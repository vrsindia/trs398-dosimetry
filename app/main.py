"""
TRS-398 Dosimetry App - Clinical Absolute Dosimetry Workflow
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.calculations.photon import (
    PhotonMeasurementInput, calculate_dose_to_water_photon,
    calculate_k_TP, calculate_k_pol, calculate_k_s_two_voltage,
)
from app.calculations.electron import ElectronMeasurementInput, calculate_dose_to_water_electron
from app.calculations.brachy import BrachyWellInput, calculate_air_kerma_strength
from app.calculations.quality_index import calculate_tpr20_10
from app.models import (
    Detector, Linac, Beam, ToleranceTable, OutputRecord,
    add_detector, get_detector, list_detectors, update_detector, delete_detector,
    add_linac, get_linac, list_linacs, update_linac, delete_linac,
    add_beam, get_beam, list_beams, update_beam, delete_beam,
    add_tolerance, list_tolerances, delete_tolerance,
    add_output_record, list_output_records,
    seed_libraries, _new_id,
)
from app.session import (
    create_session, get_session, update_session,
    SessionCorrectionFactors, DosimetrySession,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Clinical Absolute Dosimetry Workflow (IAEA TRS-398)",
    version="1.0.0",
)

templates = Jinja2Templates(directory="app/templates")
seed_libraries()


# -------------------- Home --------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


# -------------------- Linac Workflow Entry --------------------

@app.get("/linac", response_class=HTMLResponse)
async def linac_select(request: Request):
    return templates.TemplateResponse(
        request=request, name="linac_select.html",
        context={"linacs": list_linacs()},
    )


@app.get("/linac/{linac_id}", response_class=HTMLResponse)
async def linac_modality(request: Request, linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    return templates.TemplateResponse(
        request=request, name="linac_modality.html",
        context={"linac": linac},
    )


@app.get("/linac/{linac_id}/photon")
async def start_photon_session(linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    sess = create_session(linac_id=linac_id, modality="photon")
    return RedirectResponse(url=f"/session/{sess.id}/corrections", status_code=303)


@app.get("/linac/{linac_id}/electron")
async def start_electron_session(linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    sess = create_session(linac_id=linac_id, modality="electron")
    return RedirectResponse(url=f"/session/{sess.id}/corrections", status_code=303)


# -------------------- Guided Session --------------------

@app.get("/session/{session_id}/corrections", response_class=HTMLResponse)
async def session_corrections_form(request: Request, session_id: str):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    linac = get_linac(sess.linac_id)
    return templates.TemplateResponse(
        request=request, name="session_corrections.html",
        context={
            "session": sess,
            "linac": linac,
            "modality": sess.modality,
            "detectors": list_detectors(),
        },
    )


@app.post("/session/{session_id}/corrections")
async def session_corrections_calc(
    session_id: str,
    temperature_C: float = Form(...),
    pressure_hPa: float = Form(...),
    M_plus: float = Form(...),
    M_minus: float = Form(...),
    M1: float = Form(...),
    M2: float = Form(...),
    V1: float = Form(...),
    V2: float = Form(...),
    detector_id: str = Form(""),
):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    k_TP = calculate_k_TP(temperature_C, pressure_hPa)
    k_pol = calculate_k_pol(M_plus, M_minus)
    k_s = calculate_k_s_two_voltage(M1, M2, V1, V2, beam_type="pulsed")

    sess.corrections = SessionCorrectionFactors(
        k_TP=k_TP, k_pol=k_pol, k_s=k_s,
        temperature_C=temperature_C, pressure_hPa=pressure_hPa,
        calculated=True,
    )
    if detector_id:
        sess.detector_id = detector_id

    if sess.modality == "photon":
        return RedirectResponse(url=f"/session/{session_id}/quality", status_code=303)
    return RedirectResponse(url=f"/session/{session_id}/energies", status_code=303)


@app.get("/session/{session_id}/quality", response_class=HTMLResponse)
async def session_quality_form(request: Request, session_id: str):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return templates.TemplateResponse(
        request=request, name="session_quality.html",
        context={"session": sess, "qi": None},
    )


@app.post("/session/{session_id}/quality", response_class=HTMLResponse)
async def session_quality_calc(
    request: Request, session_id: str,
    dose_10: float = Form(...), dose_20: float = Form(...),
):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    qi = calculate_tpr20_10(dose_20, dose_10)
    sess.quality_index = qi.tpr20_10
    return templates.TemplateResponse(
        request=request, name="session_quality.html",
        context={"session": sess, "qi": qi},
    )


@app.get("/session/{session_id}/energies", response_class=HTMLResponse)
async def session_energies(request: Request, session_id: str):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    linac = get_linac(sess.linac_id)
    beams = list_beams(linac_id=sess.linac_id, modality=sess.modality)
    return templates.TemplateResponse(
        request=request, name="session_energies.html",
        context={"session": sess, "linac": linac, "beams": beams},
    )


@app.get("/session/{session_id}/energy/{beam_id}", response_class=HTMLResponse)
async def session_energy_form(request: Request, session_id: str, beam_id: str):
    sess = get_session(session_id)
    beam = get_beam(beam_id)
    if not sess or not beam:
        raise HTTPException(status_code=404, detail="Not found")
    linac = get_linac(sess.linac_id)
    detector = get_detector(sess.detector_id) if sess.detector_id else None
    return templates.TemplateResponse(
        request=request, name="session_energy_calc.html",
        context={
            "session": sess, "beam": beam, "linac": linac,
            "detector": detector, "result": None,
        },
    )


@dataclass
class EnergyResult:
    dose_Gy: float
    M_Q: float
    output_cGy_MU: float
    mu: float


@app.post("/session/{session_id}/energy/{beam_id}", response_class=HTMLResponse)
async def session_energy_calc(
    request: Request, session_id: str, beam_id: str,
    raw_charge_nC: float = Form(...),
    mu: float = Form(...),
    N_Dw: float = Form(...),
    k_Q: float = Form(...),
):
    sess = get_session(session_id)
    beam = get_beam(beam_id)
    if not sess or not beam:
        raise HTTPException(status_code=404, detail="Not found")
    linac = get_linac(sess.linac_id)
    detector = get_detector(sess.detector_id) if sess.detector_id else None

    corr = sess.corrections
    inp = PhotonMeasurementInput(
        raw_charge_nC=raw_charge_nC,
        N_Dw=N_Dw,
        k_Q=k_Q,
        k_pol=corr.k_pol,
        k_s=corr.k_s,
        temperature_C=corr.temperature_C,
        pressure_hPa=corr.pressure_hPa,
    )
    # Re-use photon engine for both (same formula structure)
    dose_result = calculate_dose_to_water_photon(inp)
    output_cGy_MU = (dose_result.dose_to_water_Gy * 100.0) / mu if mu > 0 else 0.0

    result = EnergyResult(
        dose_Gy=dose_result.dose_to_water_Gy,
        M_Q=dose_result.M_Q_corrected,
        output_cGy_MU=output_cGy_MU,
        mu=mu,
    )
    return templates.TemplateResponse(
        request=request, name="session_energy_calc.html",
        context={
            "session": sess, "beam": beam, "linac": linac,
            "detector": detector, "result": result,
        },
    )


@app.post("/session/{session_id}/energy/{beam_id}/tune")
async def session_energy_tune(
    session_id: str, beam_id: str,
    measured_output: float = Form(...),
    tuned_output: Optional[float] = Form(None),
    physicist: str = Form(""),
    notes: str = Form(""),
):
    sess = get_session(session_id)
    beam = get_beam(beam_id)
    if not sess or not beam:
        raise HTTPException(status_code=404, detail="Not found")

    tuning = tuned_output is not None and tuned_output > 0
    rec = OutputRecord(
        id=_new_id(),
        linac_id=sess.linac_id,
        beam_id=beam_id,
        modality=sess.modality,
        energy=beam.nominal_energy,
        date_time=datetime.utcnow().isoformat(),
        measured_output_cGy_MU=measured_output,
        tuned_output_cGy_MU=tuned_output if tuning else None,
        tuning_performed=tuning,
        detector_id=sess.detector_id,
        k_TP=sess.corrections.k_TP,
        k_pol=sess.corrections.k_pol,
        k_s=sess.corrections.k_s,
        k_Q=beam.k_Q,
        notes=notes,
        physicist=physicist,
    )
    add_output_record(rec)

    if beam.nominal_energy not in sess.completed_energies:
        sess.completed_energies.append(beam.nominal_energy)

    return RedirectResponse(url=f"/session/{session_id}/energies", status_code=303)


@app.get("/session/{session_id}/switch-modality")
async def session_switch_modality(session_id: str):
    """Reuse correction factors for the other modality."""
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    new_modality = "electron" if sess.modality == "photon" else "photon"
    new_sess = create_session(linac_id=sess.linac_id, modality=new_modality)
    # Copy shared correction factors
    new_sess.corrections = sess.corrections
    new_sess.detector_id = sess.detector_id

    if new_modality == "photon":
        return RedirectResponse(url=f"/session/{new_sess.id}/quality", status_code=303)
    return RedirectResponse(url=f"/session/{new_sess.id}/energies", status_code=303)


# -------------------- Brachy --------------------

@app.get("/brachy-select")
async def brachy_select():
    return RedirectResponse(url="/brachy", status_code=303)


@app.get("/brachy", response_class=HTMLResponse)
async def brachy_form(request: Request):
    return templates.TemplateResponse(
        request=request, name="brachy.html",
        context={"result": None, "detectors": list_detectors()},
    )

@app.post("/brachy", response_class=HTMLResponse)
async def brachy_calculate(
    request: Request,
    raw_reading: float = Form(...), N_SK: float = Form(...),
    electrometer_calibration_factor: float = Form(1.0),
    temperature_C: float = Form(20.0), pressure_hPa: float = Form(1013.25),
    k_ion: float = Form(1.0), k_other: float = Form(1.0),
    nuclide: str = Form("Ir-192"),
    calibration_datetime: Optional[str] = Form(None),
    measurement_datetime: Optional[str] = Form(None),
    integration_time_s: Optional[float] = Form(None),
):
    inp = BrachyWellInput(
        raw_reading=raw_reading, N_SK=N_SK,
        electrometer_calibration_factor=electrometer_calibration_factor,
        temperature_C=temperature_C, pressure_hPa=pressure_hPa,
        k_ion=k_ion, k_other=k_other, nuclide=nuclide,
        calibration_datetime=calibration_datetime or None,
        measurement_datetime=measurement_datetime or None,
        integration_time_s=integration_time_s,
    )
    result = calculate_air_kerma_strength(inp)
    return templates.TemplateResponse(
        request=request, name="brachy.html",
        context={"result": result, "inputs": inp, "detectors": list_detectors()},
    )


# -------------------- Detector Library --------------------

@app.get("/detectors", response_class=HTMLResponse)
async def detectors_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="detectors.html", context={"detectors": list_detectors()},
    )

@app.post("/detectors/add")
async def detector_add(
    name: str = Form(...), detector_type: str = Form(...), serial_number: str = Form(...),
    calibration_factor: float = Form(...), calibration_quality: str = Form("Co-60"),
    calibration_date: str = Form(""), calibration_lab: str = Form(""),
    next_due_date: str = Form(""), notes: str = Form(""), unit: str = Form("Gy/nC"),
):
    add_detector(Detector(
        id=_new_id(), name=name, detector_type=detector_type, serial_number=serial_number,
        calibration_factor=calibration_factor, calibration_quality=calibration_quality,
        calibration_date=calibration_date or None, calibration_lab=calibration_lab or None,
        next_due_date=next_due_date or None, notes=notes, unit=unit,
    ))
    return RedirectResponse(url="/detectors", status_code=303)

@app.post("/detectors/{det_id}/edit")
async def detector_edit(
    det_id: str, name: str = Form(...), detector_type: str = Form(...),
    serial_number: str = Form(...), calibration_factor: float = Form(...),
    calibration_quality: str = Form("Co-60"), calibration_date: str = Form(""),
    calibration_lab: str = Form(""), next_due_date: str = Form(""),
    notes: str = Form(""), unit: str = Form("Gy/nC"),
):
    update_detector(det_id, name=name, detector_type=detector_type, serial_number=serial_number,
                    calibration_factor=calibration_factor, calibration_quality=calibration_quality,
                    calibration_date=calibration_date or None, calibration_lab=calibration_lab or None,
                    next_due_date=next_due_date or None, notes=notes, unit=unit)
    return RedirectResponse(url="/detectors", status_code=303)

@app.post("/detectors/{det_id}/delete")
async def detector_delete(det_id: str):
    delete_detector(det_id)
    return RedirectResponse(url="/detectors", status_code=303)


# -------------------- Linac & Beam Library --------------------

@app.get("/linacs", response_class=HTMLResponse)
async def linacs_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="linacs.html",
        context={"linacs": list_linacs(), "beams": list_beams()},
    )

@app.post("/linacs/add")
async def linac_add(
    name: str = Form(...), manufacturer: str = Form(""), model: str = Form(""),
    serial_number: str = Form(""), location: str = Form(""), notes: str = Form(""),
):
    add_linac(Linac(id=_new_id(), name=name, manufacturer=manufacturer, model=model,
                    serial_number=serial_number, location=location, notes=notes))
    return RedirectResponse(url="/linacs", status_code=303)

@app.post("/linacs/{linac_id}/delete")
async def linac_delete(linac_id: str):
    delete_linac(linac_id)
    return RedirectResponse(url="/linacs", status_code=303)

@app.post("/beams/add")
async def beam_add(
    linac_id: str = Form(...), modality: str = Form(...), nominal_energy: str = Form(...),
    measurement_depth_cm: float = Form(...), pdd: float = Form(...), k_Q: float = Form(...),
    ssd_cm: float = Form(100.0), field_size: str = Form("10x10"), notes: str = Form(""),
):
    add_beam(Beam(id=_new_id(), linac_id=linac_id, modality=modality, nominal_energy=nominal_energy,
                  measurement_depth_cm=measurement_depth_cm, pdd=pdd, k_Q=k_Q,
                  ssd_cm=ssd_cm, field_size=field_size, notes=notes))
    return RedirectResponse(url="/linacs", status_code=303)

@app.post("/beams/{beam_id}/delete")
async def beam_delete(beam_id: str):
    delete_beam(beam_id)
    return RedirectResponse(url="/linacs", status_code=303)


# -------------------- Tolerance Library --------------------

@app.get("/tolerances", response_class=HTMLResponse)
async def tolerances_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="tolerances.html",
        context={"tolerances": list_tolerances(), "linacs": list_linacs()},
    )

@app.post("/tolerances/add")
async def tolerance_add(
    name: str = Form(...), modality: str = Form(...), parameter: str = Form("output"),
    tolerance_percent: float = Form(...), action_level_percent: Optional[float] = Form(None),
    energy: str = Form(""), linac_id: str = Form(""), notes: str = Form(""),
):
    add_tolerance(ToleranceTable(
        id=_new_id(), name=name, modality=modality, parameter=parameter,
        tolerance_percent=tolerance_percent,
        action_level_percent=action_level_percent if action_level_percent else None,
        energy=energy or None, linac_id=linac_id or None, notes=notes,
    ))
    return RedirectResponse(url="/tolerances", status_code=303)

@app.post("/tolerances/{tol_id}/delete")
async def tolerance_delete(tol_id: str):
    delete_tolerance(tol_id)
    return RedirectResponse(url="/tolerances", status_code=303)


# -------------------- Output History --------------------

@app.get("/output-history", response_class=HTMLResponse)
async def output_history(request: Request):
    return templates.TemplateResponse(
        request=request, name="output_history.html",
        context={"records": list_output_records()},
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "detectors": len(list_detectors()),
        "linacs": len(list_linacs()),
        "beams": len(list_beams()),
        "tolerances": len(list_tolerances()),
        "output_records": len(list_output_records()),
    }
