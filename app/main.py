"""
TRS-398 Dosimetry App - Clinical Absolute Dosimetry Workflow
Dark professional UI · Approval system · Tolerance colour coding
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
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
    add_detector, get_detector, list_detectors, update_detector, delete_detector,
    add_linac, get_linac, list_linacs, delete_linac,
    add_beam, get_beam, list_beams, update_beam, delete_beam,
    add_tolerance, list_tolerances, delete_tolerance, find_tolerance, check_tolerance,
    add_output_record, list_output_records,
    get_department, update_department,
    submit_change, list_pending, approve_change, reject_change,
    seed_libraries, _new_id,
)
from app.session import create_session, get_session, SessionCorrectionFactors

app = FastAPI(title="TRS-398 Dosimetry", version="1.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
seed_libraries()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


# ---- Linac workflow ----

@app.get("/linac", response_class=HTMLResponse)
async def linac_select(request: Request):
    return templates.TemplateResponse(request=request, name="linac_select.html",
                                      context={"linacs": list_linacs()})

@app.get("/linac/{linac_id}", response_class=HTMLResponse)
async def linac_modality(request: Request, linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(404, "Linac not found")
    return templates.TemplateResponse(request=request, name="linac_modality.html",
                                      context={"linac": linac})

@app.get("/linac/{linac_id}/photon")
async def start_photon(linac_id: str):
    if not get_linac(linac_id):
        raise HTTPException(404)
    sess = create_session(linac_id, "photon")
    return RedirectResponse(f"/session/{sess.id}/corrections", 303)

@app.get("/linac/{linac_id}/electron")
async def start_electron(linac_id: str):
    if not get_linac(linac_id):
        raise HTTPException(404)
    sess = create_session(linac_id, "electron")
    return RedirectResponse(f"/session/{sess.id}/corrections", 303)


# ---- Session ----

@app.get("/session/{sid}/corrections", response_class=HTMLResponse)
async def corr_form(request: Request, sid: str):
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="session_corrections.html",
        context={"session": sess, "linac": get_linac(sess.linac_id),
                 "modality": sess.modality, "detectors": list_detectors()})

@app.post("/session/{sid}/corrections")
async def corr_calc(sid: str, temperature_C: float = Form(...), pressure_hPa: float = Form(...),
                    M_plus: float = Form(...), M_minus: float = Form(...),
                    M1: float = Form(...), M2: float = Form(...),
                    V1: float = Form(...), V2: float = Form(...), detector_id: str = Form("")):
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
    if sess.modality == "photon":
        return RedirectResponse(f"/session/{sid}/quality", 303)
    return RedirectResponse(f"/session/{sid}/energies", 303)

@app.get("/session/{sid}/quality", response_class=HTMLResponse)
async def qi_form(request: Request, sid: str):
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="session_quality.html",
                                      context={"session": sess, "qi": None})

@app.post("/session/{sid}/quality", response_class=HTMLResponse)
async def qi_calc(request: Request, sid: str, dose_10: float = Form(...), dose_20: float = Form(...)):
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    qi = calculate_tpr20_10(dose_20, dose_10)
    sess.quality_index = qi.tpr20_10
    return templates.TemplateResponse(request=request, name="session_quality.html",
                                      context={"session": sess, "qi": qi})

@app.get("/session/{sid}/energies", response_class=HTMLResponse)
async def energies(request: Request, sid: str):
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="session_energies.html",
        context={"session": sess, "linac": get_linac(sess.linac_id),
                 "beams": list_beams(linac_id=sess.linac_id, modality=sess.modality)})

@app.get("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
async def energy_form(request: Request, sid: str, bid: str):
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    return templates.TemplateResponse(request=request, name="session_energy_calc.html",
        context={"session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                 "detector": get_detector(sess.detector_id) if sess.detector_id else None,
                 "result": None, "status": None})

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
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
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
    return templates.TemplateResponse(request=request, name="session_energy_calc.html",
        context={"session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                 "detector": get_detector(sess.detector_id) if sess.detector_id else None,
                 "result": result, "status": status, "tolerance": tol,
                 "nominal_output": nominal_output})

@app.post("/session/{sid}/energy/{bid}/tune")
async def energy_tune(sid: str, bid: str, measured_output: float = Form(...),
                      tuned_output: Optional[float] = Form(None),
                      nominal_output: float = Form(1.0),
                      physicist: str = Form(""), notes: str = Form("")):
    sess, beam = get_session(sid), get_beam(bid)
    if not sess or not beam:
        raise HTTPException(404)
    tuning = tuned_output is not None and tuned_output > 0
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
        k_Q=beam.k_Q, notes=notes, physicist=physicist,
        nominal_output_cGy_MU=nominal_output, status=status))
    if beam.nominal_energy not in sess.completed_energies:
        sess.completed_energies.append(beam.nominal_energy)
    return RedirectResponse(f"/session/{sid}/energies", 303)

@app.get("/session/{sid}/switch-modality")
async def switch_mod(sid: str):
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404)
    new_mod = "electron" if sess.modality == "photon" else "photon"
    ns = create_session(sess.linac_id, new_mod)
    ns.corrections = sess.corrections
    ns.detector_id = sess.detector_id
    if new_mod == "photon":
        return RedirectResponse(f"/session/{ns.id}/quality", 303)
    return RedirectResponse(f"/session/{ns.id}/energies", 303)


# ---- Brachy ----

@app.get("/brachy", response_class=HTMLResponse)
async def brachy_form(request: Request):
    return templates.TemplateResponse(request=request, name="brachy.html",
                                      context={"result": None, "detectors": list_detectors()})

@app.post("/brachy", response_class=HTMLResponse)
async def brachy_calc(request: Request, raw_reading: float = Form(...), N_SK: float = Form(...),
                      electrometer_calibration_factor: float = Form(1.0),
                      temperature_C: float = Form(20.0), pressure_hPa: float = Form(1013.25),
                      k_ion: float = Form(1.0), k_other: float = Form(1.0),
                      nuclide: str = Form("Ir-192"),
                      calibration_datetime: Optional[str] = Form(None),
                      measurement_datetime: Optional[str] = Form(None),
                      integration_time_s: Optional[float] = Form(None)):
    inp = BrachyWellInput(raw_reading=raw_reading, N_SK=N_SK,
        electrometer_calibration_factor=electrometer_calibration_factor,
        temperature_C=temperature_C, pressure_hPa=pressure_hPa, k_ion=k_ion, k_other=k_other,
        nuclide=nuclide, calibration_datetime=calibration_datetime or None,
        measurement_datetime=measurement_datetime or None, integration_time_s=integration_time_s)
    result = calculate_air_kerma_strength(inp)
    return templates.TemplateResponse(request=request, name="brachy.html",
        context={"result": result, "inputs": inp, "detectors": list_detectors()})


# ---- Detectors ----

@app.get("/detectors", response_class=HTMLResponse)
async def detectors_page(request: Request):
    return templates.TemplateResponse(request=request, name="detectors.html",
                                      context={"detectors": list_detectors()})

@app.post("/detectors/add")
async def det_add(name: str = Form(...), detector_type: str = Form(...),
                  serial_number: str = Form(...), calibration_factor: float = Form(...),
                  calibration_quality: str = Form("Co-60"), calibration_date: str = Form(""),
                  calibration_lab: str = Form(""), next_due_date: str = Form(""),
                  notes: str = Form(""), unit: str = Form("Gy/nC")):
    add_detector(Detector(id=_new_id(), name=name, detector_type=detector_type,
        serial_number=serial_number, calibration_factor=calibration_factor,
        calibration_quality=calibration_quality, calibration_date=calibration_date or None,
        calibration_lab=calibration_lab or None, next_due_date=next_due_date or None,
        notes=notes, unit=unit))
    return RedirectResponse("/detectors", 303)

@app.post("/detectors/{did}/edit")
async def det_edit(did: str, name: str = Form(...), detector_type: str = Form(...),
                   serial_number: str = Form(...), calibration_factor: float = Form(...),
                   calibration_quality: str = Form("Co-60"), calibration_date: str = Form(""),
                   calibration_lab: str = Form(""), next_due_date: str = Form(""),
                   notes: str = Form(""), unit: str = Form("Gy/nC"), requested_by: str = Form("")):
    det = get_detector(did)
    if not det:
        raise HTTPException(404)
    proposed = dict(name=name, detector_type=detector_type, serial_number=serial_number,
                    calibration_factor=calibration_factor, calibration_quality=calibration_quality,
                    calibration_date=calibration_date or None, calibration_lab=calibration_lab or None,
                    next_due_date=next_due_date or None, notes=notes, unit=unit)
    submit_change("detector", did, "update", proposed, det.__dict__, requested_by)
    return RedirectResponse("/approvals", 303)

@app.post("/detectors/{did}/delete")
async def det_del(did: str):
    delete_detector(did)
    return RedirectResponse("/detectors", 303)


# ---- Linacs & Beams ----

@app.get("/linacs", response_class=HTMLResponse)
async def linacs_page(request: Request):
    return templates.TemplateResponse(request=request, name="linacs.html",
        context={"linacs": list_linacs(), "beams": list_beams()})

@app.post("/linacs/add")
async def linac_add(name: str = Form(...), manufacturer: str = Form(""),
                    model: str = Form(""), serial_number: str = Form(""),
                    location: str = Form(""), notes: str = Form("")):
    add_linac(Linac(id=_new_id(), name=name, manufacturer=manufacturer, model=model,
                    serial_number=serial_number, location=location, notes=notes))
    return RedirectResponse("/linacs", 303)

@app.post("/linacs/{lid}/delete")
async def linac_del(lid: str):
    delete_linac(lid)
    return RedirectResponse("/linacs", 303)

@app.post("/beams/add")
async def beam_add(linac_id: str = Form(...), modality: str = Form(...),
                   nominal_energy: str = Form(...), measurement_depth_cm: float = Form(...),
                   pdd: float = Form(...), k_Q: float = Form(...),
                   ssd_cm: float = Form(100.0), field_size: str = Form("10x10"), notes: str = Form("")):
    add_beam(Beam(id=_new_id(), linac_id=linac_id, modality=modality,
                  nominal_energy=nominal_energy, measurement_depth_cm=measurement_depth_cm,
                  pdd=pdd, k_Q=k_Q, ssd_cm=ssd_cm, field_size=field_size, notes=notes))
    return RedirectResponse("/linacs", 303)

@app.post("/beams/{bid}/edit")
async def beam_edit(bid: str, nominal_energy: str = Form(...),
                    measurement_depth_cm: float = Form(...), pdd: float = Form(...),
                    k_Q: float = Form(...), ssd_cm: float = Form(100.0),
                    field_size: str = Form("10x10"), notes: str = Form(""),
                    requested_by: str = Form("")):
    beam = get_beam(bid)
    if not beam:
        raise HTTPException(404)
    proposed = dict(nominal_energy=nominal_energy, measurement_depth_cm=measurement_depth_cm,
                    pdd=pdd, k_Q=k_Q, ssd_cm=ssd_cm, field_size=field_size, notes=notes)
    submit_change("beam", bid, "update", proposed, beam.__dict__, requested_by)
    return RedirectResponse("/approvals", 303)

@app.post("/beams/{bid}/delete")
async def beam_del(bid: str):
    delete_beam(bid)
    return RedirectResponse("/linacs", 303)


# ---- Tolerances ----

@app.get("/tolerances", response_class=HTMLResponse)
async def tol_page(request: Request):
    return templates.TemplateResponse(request=request, name="tolerances.html",
        context={"tolerances": list_tolerances(), "linacs": list_linacs()})

@app.post("/tolerances/add")
async def tol_add(name: str = Form(...), modality: str = Form(...),
                  parameter: str = Form("output"), tolerance_percent: float = Form(...),
                  action_level_percent: Optional[float] = Form(None),
                  energy: str = Form(""), linac_id: str = Form(""), notes: str = Form("")):
    add_tolerance(ToleranceTable(id=_new_id(), name=name, modality=modality, parameter=parameter,
        tolerance_percent=tolerance_percent,
        action_level_percent=action_level_percent if action_level_percent else None,
        energy=energy or None, linac_id=linac_id or None, notes=notes))
    return RedirectResponse("/tolerances", 303)

@app.post("/tolerances/{tid}/delete")
async def tol_del(tid: str):
    delete_tolerance(tid)
    return RedirectResponse("/tolerances", 303)


# ---- Department ----

@app.get("/department", response_class=HTMLResponse)
async def dept_page(request: Request):
    return templates.TemplateResponse(request=request, name="department.html",
                                      context={"dept": get_department()})

@app.post("/department/edit")
async def dept_edit(name: str = Form(""), hospital: str = Form(""), address: str = Form(""),
                    city: str = Form(""), country: str = Form(""), phone: str = Form(""),
                    email: str = Form(""), head_physicist: str = Form(""),
                    notes: str = Form(""), requested_by: str = Form("")):
    proposed = dict(name=name, hospital=hospital, address=address, city=city, country=country,
                    phone=phone, email=email, head_physicist=head_physicist, notes=notes)
    submit_change("department", "dept", "update", proposed, get_department().__dict__, requested_by)
    return RedirectResponse("/approvals", 303)


# ---- Approvals ----

@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request):
    return templates.TemplateResponse(request=request, name="approvals.html",
                                      context={"pending": list_pending()})

@app.post("/approvals/{pid}/approve")
async def do_approve(pid: str, reviewed_by: str = Form("Physicist")):
    approve_change(pid, reviewed_by)
    return RedirectResponse("/approvals", 303)

@app.post("/approvals/{pid}/reject")
async def do_reject(pid: str, reviewed_by: str = Form("Physicist")):
    reject_change(pid, reviewed_by)
    return RedirectResponse("/approvals", 303)


# ---- Output History ----

@app.get("/output-history", response_class=HTMLResponse)
async def out_hist(request: Request):
    return templates.TemplateResponse(request=request, name="output_history.html",
                                      context={"records": list_output_records()})


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0",
            "detectors": len(list_detectors()), "linacs": len(list_linacs()),
            "pending": len(list_pending())}
