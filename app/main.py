"""
DOSE pro – Clinical Dosimetry Solution
"""

from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

from app.calculations.photon import (
    PhotonMeasurementInput, calculate_dose_to_water_photon,
    calculate_k_TP, calculate_k_pol, calculate_k_s_two_voltage,
)
from app.calculations.brachy import BrachyWellInput, calculate_air_kerma_strength
from app.calculations.quality_index import calculate_tpr20_10
from app.models import (
    Detector, Linac, Beam, ToleranceTable, OutputRecord,
    add_detector, get_detector, list_detectors, delete_detector,
    add_linac, get_linac, list_linacs, delete_linac,
    add_beam, get_beam, list_beams, delete_beam,
    add_tolerance, list_tolerances, delete_tolerance, find_tolerance, check_tolerance, get_tolerance,
    add_output_record, list_output_records,
    get_department,
    submit_change, list_pending, approve_change, reject_change,
    seed_libraries, _new_id,
)
from app.session import create_session, get_session, SessionCorrectionFactors
from app.auth import (
    seed_users, authenticate, create_session_token, get_user_by_token, destroy_session,
    create_user, list_users, get_user, update_user, delete_user,
    ROLES, DEFAULT_PERMISSIONS,
    PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW, PERM_ADMIN_PANEL,
)

app = FastAPI(title="DOSE pro", version="1.3.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
seed_libraries()
seed_users()

COOKIE = "dosepro_session"

def _user(request: Request):
    return get_user_by_token(request.cookies.get(COOKIE))

def _require(request: Request, perm: Optional[str] = None):
    user = _user(request)
    if not user:
        return None
    if perm and not user.has(perm):
        raise HTTPException(403, "Insufficient permissions")
    return user

def _login_redirect():
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _user(request):
        return RedirectResponse("/", 303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate(username, password)
    if not user:
        return templates.TemplateResponse(request=request, name="login.html",
                                          context={"error": "Invalid username or password"})
    token = create_session_token(user.id)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=86400 * 7)
    return resp

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        destroy_session(token)
    resp = RedirectResponse("/login", 303)
    resp.delete_cookie(COOKIE)
    return resp

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = _user(request)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="index.html", context={"current_user": user})


# ---- Users ----

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    user = _require(request, PERM_ADMIN_PANEL)
    if not user:
        return _login_redirect()
    all_perms = sorted({p for perms in DEFAULT_PERMISSIONS.values() for p in perms})
    return templates.TemplateResponse(request=request, name="users.html", context={
        "current_user": user, "users": list_users(), "roles": ROLES, "all_perms": all_perms,
        "pw_message": None, "pw_error": None,
    })

@app.post("/users/change-password", response_class=HTMLResponse)
async def change_my_password(request: Request, current_password: str = Form(...),
                             new_password: str = Form(...), confirm_password: str = Form(...)):
    user = _require(request, PERM_ADMIN_PANEL)
    if not user:
        return _login_redirect()
    all_perms = sorted({p for perms in DEFAULT_PERMISSIONS.values() for p in perms})
    ctx = {"current_user": user, "users": list_users(), "roles": ROLES, "all_perms": all_perms,
           "pw_message": None, "pw_error": None}
    if new_password != confirm_password:
        ctx["pw_error"] = "New passwords do not match"
        return templates.TemplateResponse(request=request, name="users.html", context=ctx)
    if len(new_password) < 6:
        ctx["pw_error"] = "Password must be at least 6 characters"
        return templates.TemplateResponse(request=request, name="users.html", context=ctx)
    if not user.check_password(current_password):
        ctx["pw_error"] = "Current password is incorrect"
        return templates.TemplateResponse(request=request, name="users.html", context=ctx)
    update_user(user.id, password=new_password)
    ctx["pw_message"] = "Password updated successfully"
    ctx["current_user"] = get_user(user.id)
    return templates.TemplateResponse(request=request, name="users.html", context=ctx)

@app.post("/users/add")
async def users_add(request: Request, username: str = Form(...), password: str = Form(...),
                    full_name: str = Form(...), role: str = Form(...)):
    user = _require(request, PERM_USER_MANAGE)
    if not user:
        return _login_redirect()
    try:
        create_user(username, password, full_name, role, created_by=user.username)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse("/users", 303)

@app.post("/users/{uid}/edit")
async def users_edit(request: Request, uid: str, full_name: str = Form(...),
                     role: str = Form(...), password: str = Form(""),
                     active: Optional[str] = Form(None),
                     permissions: List[str] = Form([])):
    user = _require(request, PERM_USER_MANAGE)
    if not user:
        return _login_redirect()
    kwargs = dict(full_name=full_name, role=role, active=bool(active),
                permissions=set(permissions) if permissions else set())
    if password:
        kwargs["password"] = password
    update_user(uid, **kwargs)
    return RedirectResponse("/users", 303)

@app.post("/users/{uid}/delete")
async def users_del(request: Request, uid: str):
    user = _require(request, PERM_USER_MANAGE)
    if not user:
        return _login_redirect()
    try:
        delete_user(uid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse("/users", 303)


# ---- Linac workflow ----

@app.get("/linac", response_class=HTMLResponse)
async def linac_select(request: Request):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="linac_select.html",
                                      context={"linacs": list_linacs(), "current_user": user})

@app.get("/linac/{linac_id}", response_class=HTMLResponse)
async def linac_modality(request: Request, linac_id: str):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="linac_modality.html",
                                      context={"linac": linac, "current_user": user})

@app.get("/linac/{linac_id}/photon")
async def start_photon(request: Request, linac_id: str):
    if not _require(request, PERM_CALCULATE):
        return _login_redirect()
    if not get_linac(linac_id):
        raise HTTPException(404)
    sess = create_session(linac_id, "photon")
    return RedirectResponse(f"/session/{sess.id}/corrections", 303)

@app.get("/linac/{linac_id}/electron")
async def start_electron(request: Request, linac_id: str):
    if not _require(request, PERM_CALCULATE):
        return _login_redirect()
    if not get_linac(linac_id):
        raise HTTPException(404)
    sess = create_session(linac_id, "electron")
    return RedirectResponse(f"/session/{sess.id}/corrections", 303)


# ---- Session: corrections then energies (TPR per photon beam) ----

@app.get("/session/{sid}/corrections", response_class=HTMLResponse)
async def corr_form(request: Request, sid: str):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="session_corrections.html",
        context={"session": sess, "linac": get_linac(sess.linac_id), "modality": sess.modality,
                 "detectors": list_detectors(), "current_user": user})

@app.post("/session/{sid}/corrections")
async def corr_calc(request: Request, sid: str, temperature_C: float = Form(...),
                    pressure_hPa: float = Form(...), M_plus: float = Form(...),
                    M_minus: float = Form(...), M1: float = Form(...), M2: float = Form(...),
                    V1: float = Form(...), V2: float = Form(...), detector_id: str = Form("")):
    if not _require(request, PERM_CALCULATE):
        return _login_redirect()
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    sess.corrections = SessionCorrectionFactors(
        k_TP=calculate_k_TP(temperature_C, pressure_hPa),
        k_pol=calculate_k_pol(M_plus, M_minus),
        k_s=calculate_k_s_two_voltage(M1, M2, V1, V2),
        temperature_C=temperature_C, pressure_hPa=pressure_hPa, calculated=True)
    if detector_id:
        sess.detector_id = detector_id
    # Photons: go to energy list; TPR is per beam
    return RedirectResponse(f"/session/{sid}/energies", 303)

@app.get("/session/{sid}/energies", response_class=HTMLResponse)
async def energies(request: Request, sid: str):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    detector = get_detector(sess.detector_id) if sess.detector_id else None
    return templates.TemplateResponse(request=request, name="session_energies.html",
        context={"session": sess, "linac": get_linac(sess.linac_id),
                 "beams": list_beams(linac_id=sess.linac_id, modality=sess.modality),
                 "detector": detector, "current_user": user})

# Per-beam TPR20,10
@app.get("/session/{sid}/beam/{bid}/quality", response_class=HTMLResponse)
async def beam_qi_form(request: Request, sid: str, bid: str):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    existing = sess.beam_quality_index.get(bid)
    return templates.TemplateResponse(request=request, name="session_beam_qi.html",
        context={"session": sess, "beam": beam, "qi": None, "existing_qi": existing, "current_user": user})

@app.post("/session/{sid}/beam/{bid}/quality", response_class=HTMLResponse)
async def beam_qi_calc(request: Request, sid: str, bid: str,
                       dose_10: float = Form(...), dose_20: float = Form(...)):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    qi = calculate_tpr20_10(dose_20, dose_10)
    sess.beam_quality_index[bid] = qi.tpr20_10
    # Optionally store on beam library
    from app.models import update_beam
    update_beam(bid, quality_index=qi.tpr20_10)
    return templates.TemplateResponse(request=request, name="session_beam_qi.html",
        context={"session": sess, "beam": beam, "qi": qi, "existing_qi": qi.tpr20_10, "current_user": user})

@app.get("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
async def energy_form(request: Request, sid: str, bid: str):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    detector = get_detector(sess.detector_id) if sess.detector_id else None
    beam_qi = sess.beam_quality_index.get(bid) or beam.quality_index
    return templates.TemplateResponse(request=request, name="session_energy_calc.html",
        context={"session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                 "detector": detector, "beam_qi": beam_qi,
                 "result": None, "status": None, "current_user": user})

@dataclass
class EnergyResult:
    dose_Gy: float
    M_Q: float
    output_cGy_MU: float
    mu: float

@app.post("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
async def energy_calc(request: Request, sid: str, bid: str,
                      raw_charge_nC: float = Form(...), mu: float = Form(...),
                      N_Dw: float = Form(...), k_Q: float = Form(...),
                      nominal_output: float = Form(1.0)):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    detector = get_detector(sess.detector_id) if sess.detector_id else None
    # Prefer N_Dw from detector library when detector is selected
    if detector:
        N_Dw = detector.calibration_factor
    corr = sess.corrections
    inp = PhotonMeasurementInput(
        raw_charge_nC=raw_charge_nC, N_Dw=N_Dw, k_Q=k_Q,
        k_pol=corr.k_pol, k_s=corr.k_s,
        temperature_C=corr.temperature_C, pressure_hPa=corr.pressure_hPa)
    dr = calculate_dose_to_water_photon(inp)
    out = (dr.dose_to_water_Gy * 100.0) / mu if mu > 0 else 0.0
    result = EnergyResult(dose_Gy=dr.dose_to_water_Gy, M_Q=dr.M_Q_corrected,
                          output_cGy_MU=out, mu=mu)
    tol = find_tolerance(sess.modality, beam.nominal_energy, sess.linac_id)
    status = check_tolerance(out, nominal_output, tol)
    beam_qi = sess.beam_quality_index.get(bid) or beam.quality_index
    return templates.TemplateResponse(request=request, name="session_energy_calc.html",
        context={"session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                 "detector": detector, "beam_qi": beam_qi,
                 "result": result, "status": status, "tolerance": tol,
                 "nominal_output": nominal_output, "current_user": user})

@app.post("/session/{sid}/energy/{bid}/tune")
async def energy_tune(request: Request, sid: str, bid: str,
                      measured_output: float = Form(...),
                      tuned_output: Optional[float] = Form(None),
                      nominal_output: float = Form(1.0),
                      physicist: str = Form(""), notes: str = Form("")):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    can_tune = user.has(PERM_TUNE)
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    tuning = can_tune and tuned_output is not None and tuned_output > 0
    final = tuned_output if tuning else measured_output
    tol = find_tolerance(sess.modality, beam.nominal_energy, sess.linac_id)
    status = check_tolerance(final, nominal_output, tol)
    add_output_record(OutputRecord(
        id=_new_id(), linac_id=sess.linac_id, beam_id=bid, modality=sess.modality,
        energy=beam.nominal_energy, date_time=datetime.utcnow().isoformat(),
        measured_output_cGy_MU=measured_output,
        tuned_output_cGy_MU=tuned_output if tuning else None,
        tuning_performed=tuning, detector_id=sess.detector_id,
        k_TP=sess.corrections.k_TP, k_pol=sess.corrections.k_pol, k_s=sess.corrections.k_s,
        k_Q=beam.k_Q, notes=notes, physicist=physicist or user.full_name,
        nominal_output_cGy_MU=nominal_output, status=status))
    if beam.nominal_energy not in sess.completed_energies:
        sess.completed_energies.append(beam.nominal_energy)
    return RedirectResponse(f"/session/{sid}/energies", 303)

@app.get("/session/{sid}/switch-modality")
async def switch_mod(request: Request, sid: str):
    if not _require(request, PERM_CALCULATE):
        return _login_redirect()
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    new_mod = "electron" if sess.modality == "photon" else "photon"
    ns = create_session(sess.linac_id, new_mod)
    ns.corrections = sess.corrections
    ns.detector_id = sess.detector_id
    return RedirectResponse(f"/session/{ns.id}/energies", 303)


# ---- Brachy ----

@app.get("/brachy", response_class=HTMLResponse)
async def brachy_form(request: Request):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="brachy.html",
        context={"result": None, "detectors": list_detectors(), "current_user": user})

@app.post("/brachy", response_class=HTMLResponse)
async def brachy_calc(request: Request, raw_reading: float = Form(...), N_SK: float = Form(...),
                      electrometer_calibration_factor: float = Form(1.0),
                      temperature_C: float = Form(20.0), pressure_hPa: float = Form(1013.25),
                      k_ion: float = Form(1.0), k_other: float = Form(1.0),
                      nuclide: str = Form("Ir-192"),
                      calibration_datetime: Optional[str] = Form(None),
                      measurement_datetime: Optional[str] = Form(None),
                      integration_time_s: Optional[float] = Form(None)):
    user = _require(request, PERM_CALCULATE)
    if not user:
        return _login_redirect()
    # Prefer well chamber N_SK from detector library if matching
    inp = BrachyWellInput(raw_reading=raw_reading, N_SK=N_SK,
        electrometer_calibration_factor=electrometer_calibration_factor,
        temperature_C=temperature_C, pressure_hPa=pressure_hPa, k_ion=k_ion, k_other=k_other,
        nuclide=nuclide, calibration_datetime=calibration_datetime or None,
        measurement_datetime=measurement_datetime or None, integration_time_s=integration_time_s)
    result = calculate_air_kerma_strength(inp)
    return templates.TemplateResponse(request=request, name="brachy.html",
        context={"result": result, "inputs": inp, "detectors": list_detectors(), "current_user": user})


# ---- Libraries ----

@app.get("/detectors", response_class=HTMLResponse)
async def detectors_page(request: Request):
    user = _require(request, PERM_LIBRARY_VIEW)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="detectors.html",
                                      context={"detectors": list_detectors(), "current_user": user})

@app.post("/detectors/add")
async def det_add(request: Request, name: str = Form(...), detector_type: str = Form(...),
                  serial_number: str = Form(...), calibration_factor: float = Form(...),
                  calibration_quality: str = Form("Co-60"), calibration_date: str = Form(""),
                  calibration_lab: str = Form(""), next_due_date: str = Form(""),
                  notes: str = Form(""), unit: str = Form("Gy/nC")):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    add_detector(Detector(id=_new_id(), name=name, detector_type=detector_type,
        serial_number=serial_number, calibration_factor=calibration_factor,
        calibration_quality=calibration_quality, calibration_date=calibration_date or None,
        calibration_lab=calibration_lab or None, next_due_date=next_due_date or None,
        notes=notes, unit=unit))
    return RedirectResponse("/detectors", 303)

@app.post("/detectors/{did}/edit")
async def det_edit(request: Request, did: str, name: str = Form(...),
                   detector_type: str = Form(...), serial_number: str = Form(...),
                   calibration_factor: float = Form(...), calibration_quality: str = Form("Co-60"),
                   calibration_date: str = Form(""), calibration_lab: str = Form(""),
                   next_due_date: str = Form(""), notes: str = Form(""),
                   unit: str = Form("Gy/nC"), requested_by: str = Form("")):
    user = _require(request, PERM_LIBRARY_EDIT)
    if not user:
        return _login_redirect()
    det = get_detector(did)
    if not det:
        raise HTTPException(404)
    proposed = dict(name=name, detector_type=detector_type, serial_number=serial_number,
                    calibration_factor=calibration_factor, calibration_quality=calibration_quality,
                    calibration_date=calibration_date or None, calibration_lab=calibration_lab or None,
                    next_due_date=next_due_date or None, notes=notes, unit=unit)
    submit_change("detector", did, "update", proposed, det.__dict__, requested_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.post("/detectors/{did}/delete")
async def det_del(request: Request, did: str):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    delete_detector(did)
    return RedirectResponse("/detectors", 303)


@app.get("/linacs", response_class=HTMLResponse)
async def linacs_page(request: Request):
    user = _require(request, PERM_LIBRARY_VIEW)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="linacs.html",
        context={"linacs": list_linacs(), "beams": list_beams(),
                 "tolerances": list_tolerances(), "current_user": user})

@app.post("/linacs/add")
async def linac_add(request: Request, name: str = Form(...), manufacturer: str = Form(""),
                    model: str = Form(""), serial_number: str = Form(""),
                    location: str = Form(""), notes: str = Form("")):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    add_linac(Linac(id=_new_id(), name=name, manufacturer=manufacturer, model=model,
                    serial_number=serial_number, location=location, notes=notes))
    return RedirectResponse("/linacs", 303)

@app.post("/linacs/{lid}/delete")
async def linac_del(request: Request, lid: str):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    delete_linac(lid)
    return RedirectResponse("/linacs", 303)

@app.post("/beams/add")
async def beam_add(request: Request, linac_id: str = Form(...), modality: str = Form(...),
                   nominal_energy: str = Form(...), measurement_depth_cm: float = Form(...),
                   pdd: float = Form(...), k_Q: float = Form(...),
                   ssd_cm: float = Form(100.0), field_size: str = Form("10x10"), notes: str = Form("")):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    add_beam(Beam(id=_new_id(), linac_id=linac_id, modality=modality,
                  nominal_energy=nominal_energy, measurement_depth_cm=measurement_depth_cm,
                  pdd=pdd, k_Q=k_Q, ssd_cm=ssd_cm, field_size=field_size, notes=notes))
    return RedirectResponse("/linacs", 303)

@app.post("/beams/{bid}/edit")
async def beam_edit(request: Request, bid: str, nominal_energy: str = Form(...),
                    measurement_depth_cm: float = Form(...), pdd: float = Form(...),
                    k_Q: float = Form(...), ssd_cm: float = Form(100.0),
                    field_size: str = Form("10x10"), notes: str = Form(""),
                    requested_by: str = Form("")):
    user = _require(request, PERM_LIBRARY_EDIT)
    if not user:
        return _login_redirect()
    beam = get_beam(bid)
    if not beam:
        raise HTTPException(404)
    proposed = dict(nominal_energy=nominal_energy, measurement_depth_cm=measurement_depth_cm,
                    pdd=pdd, k_Q=k_Q, ssd_cm=ssd_cm, field_size=field_size, notes=notes)
    submit_change("beam", bid, "update", proposed, beam.__dict__, requested_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.post("/beams/{bid}/delete")
async def beam_del(request: Request, bid: str):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    delete_beam(bid)
    return RedirectResponse("/linacs", 303)


@app.get("/tolerances", response_class=HTMLResponse)
async def tol_page(request: Request):
    user = _require(request, PERM_LIBRARY_VIEW)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="tolerances.html",
        context={"tolerances": list_tolerances(), "linacs": list_linacs(), "current_user": user})

@app.post("/tolerances/add")
async def tol_add(request: Request, name: str = Form(...), modality: str = Form(...),
                  parameter: str = Form("output"), tolerance_percent: float = Form(...),
                  action_level_percent: Optional[float] = Form(None),
                  energy: str = Form(""), linac_id: str = Form(""), notes: str = Form("")):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    add_tolerance(ToleranceTable(id=_new_id(), name=name, modality=modality, parameter=parameter,
        tolerance_percent=tolerance_percent,
        action_level_percent=action_level_percent if action_level_percent else None,
        energy=energy or None, linac_id=linac_id or None, notes=notes))
    return RedirectResponse("/tolerances", 303)

@app.post("/tolerances/{tid}/edit")
async def tol_edit(request: Request, tid: str, name: str = Form(...), modality: str = Form(...),
                   tolerance_percent: float = Form(...),
                   action_level_percent: Optional[float] = Form(None),
                   energy: str = Form(""), notes: str = Form(""),
                   requested_by: str = Form("")):
    user = _require(request, PERM_LIBRARY_EDIT)
    if not user:
        return _login_redirect()
    tol = get_tolerance(tid)
    if not tol:
        raise HTTPException(404)
    proposed = dict(name=name, modality=modality, tolerance_percent=tolerance_percent,
                    action_level_percent=action_level_percent if action_level_percent else None,
                    energy=energy or None, notes=notes)
    submit_change("tolerance", tid, "update", proposed, tol.__dict__, requested_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.post("/tolerances/{tid}/delete")
async def tol_del(request: Request, tid: str):
    if not _require(request, PERM_LIBRARY_EDIT):
        return _login_redirect()
    delete_tolerance(tid)
    return RedirectResponse("/tolerances", 303)


@app.get("/department", response_class=HTMLResponse)
async def dept_page(request: Request):
    user = _user(request)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="department.html",
                                      context={"dept": get_department(), "current_user": user})

@app.post("/department/edit")
async def dept_edit(request: Request, name: str = Form(""), hospital: str = Form(""),
                    address: str = Form(""), city: str = Form(""), country: str = Form(""),
                    phone: str = Form(""), email: str = Form(""),
                    head_physicist: str = Form(""), notes: str = Form(""),
                    requested_by: str = Form("")):
    user = _require(request, PERM_DEPT_EDIT)
    if not user:
        return _login_redirect()
    proposed = dict(name=name, hospital=hospital, address=address, city=city, country=country,
                    phone=phone, email=email, head_physicist=head_physicist, notes=notes)
    submit_change("department", "dept", "update", proposed, get_department().__dict__,
                  requested_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request):
    user = _require(request, PERM_APPROVE)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="approvals.html",
                                      context={"pending": list_pending(), "current_user": user})

@app.post("/approvals/{pid}/approve")
async def do_approve(request: Request, pid: str, reviewed_by: str = Form("")):
    user = _require(request, PERM_APPROVE)
    if not user:
        return _login_redirect()
    approve_change(pid, reviewed_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.post("/approvals/{pid}/reject")
async def do_reject(request: Request, pid: str, reviewed_by: str = Form("")):
    user = _require(request, PERM_APPROVE)
    if not user:
        return _login_redirect()
    reject_change(pid, reviewed_by or user.full_name)
    return RedirectResponse("/approvals", 303)

@app.get("/output-history", response_class=HTMLResponse)
async def out_hist(request: Request):
    user = _require(request, PERM_HISTORY_VIEW)
    if not user:
        return _login_redirect()
    return templates.TemplateResponse(request=request, name="output_history.html",
                                      context={"records": list_output_records(), "current_user": user})

@app.get("/health")
async def health():
    return {"status": "ok", "app": "DOSE pro", "version": "1.3.0"}
