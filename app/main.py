"""
TRS-398 Dosimetry App - Clinical Absolute Dosimetry Workflow
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

from app.calculations.photon import PhotonMeasurementInput, calculate_dose_to_water_photon
from app.calculations.electron import ElectronMeasurementInput, calculate_dose_to_water_electron
from app.calculations.brachy import BrachyWellInput, calculate_air_kerma_strength
from app.models import (
    Detector, Linac, Beam, ToleranceTable, OutputRecord,
    add_detector, get_detector, list_detectors, update_detector, delete_detector,
    add_linac, get_linac, list_linacs, update_linac, delete_linac,
    add_beam, get_beam, list_beams, update_beam, delete_beam,
    add_tolerance, list_tolerances, delete_tolerance,
    add_output_record, list_output_records,
    seed_libraries, _new_id,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Clinical Absolute Dosimetry Workflow (IAEA TRS-398)",
    version="0.9.0",
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
        request=request,
        name="linac_select.html",
        context={"linacs": list_linacs()},
    )


@app.get("/linac/{linac_id}", response_class=HTMLResponse)
async def linac_modality(request: Request, linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    return templates.TemplateResponse(
        request=request,
        name="linac_modality.html",
        context={"linac": linac},
    )


# -------------------- Photon / Electron calculation pages (existing, kept for now) --------------------

@app.get("/linac/{linac_id}/photon", response_class=HTMLResponse)
async def linac_photon(request: Request, linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    return templates.TemplateResponse(
        request=request,
        name="photon.html",
        context={
            "result": None,
            "linac": linac,
            "detectors": list_detectors(),
            "beams": list_beams(linac_id=linac_id, modality="photon"),
        },
    )


@app.get("/linac/{linac_id}/electron", response_class=HTMLResponse)
async def linac_electron(request: Request, linac_id: str):
    linac = get_linac(linac_id)
    if not linac:
        raise HTTPException(status_code=404, detail="Linac not found")
    return templates.TemplateResponse(
        request=request,
        name="electron.html",
        context={
            "result": None,
            "linac": linac,
            "detectors": list_detectors(),
            "beams": list_beams(linac_id=linac_id, modality="electron"),
        },
    )


# Keep old direct routes for compatibility
@app.get("/photon", response_class=HTMLResponse)
async def photon_form(request: Request):
    return templates.TemplateResponse(
        request=request, name="photon.html",
        context={"result": None, "detectors": list_detectors(), "beams": list_beams(modality="photon")},
    )

@app.post("/photon", response_class=HTMLResponse)
async def photon_calculate(
    request: Request,
    raw_charge_nC: float = Form(...),
    N_Dw: float = Form(...),
    k_Q: float = Form(...),
    electrometer_calibration_factor: float = Form(1.0),
    k_pol: float = Form(1.0),
    k_s: float = Form(1.0),
    temperature_C: float = Form(20.0),
    pressure_hPa: float = Form(1013.25),
    k_other: float = Form(1.0),
):
    inp = PhotonMeasurementInput(
        raw_charge_nC=raw_charge_nC, N_Dw=N_Dw, k_Q=k_Q,
        electrometer_calibration_factor=electrometer_calibration_factor,
        k_pol=k_pol, k_s=k_s, temperature_C=temperature_C,
        pressure_hPa=pressure_hPa, k_other=k_other,
    )
    result = calculate_dose_to_water_photon(inp)
    return templates.TemplateResponse(
        request=request, name="photon.html",
        context={"result": result, "inputs": inp, "detectors": list_detectors(), "beams": list_beams(modality="photon")},
    )


@app.get("/electron", response_class=HTMLResponse)
async def electron_form(request: Request):
    return templates.TemplateResponse(
        request=request, name="electron.html",
        context={"result": None, "detectors": list_detectors(), "beams": list_beams(modality="electron")},
    )

@app.post("/electron", response_class=HTMLResponse)
async def electron_calculate(
    request: Request,
    raw_charge_nC: float = Form(...),
    N_Dw: float = Form(...),
    k_Q: float = Form(...),
    electrometer_calibration_factor: float = Form(1.0),
    k_pol: float = Form(1.0),
    k_s: float = Form(1.0),
    temperature_C: float = Form(20.0),
    pressure_hPa: float = Form(1013.25),
    k_other: float = Form(1.0),
    R50_cm: Optional[float] = Form(None),
    nominal_energy_MeV: Optional[float] = Form(None),
):
    inp = ElectronMeasurementInput(
        raw_charge_nC=raw_charge_nC, N_Dw=N_Dw, k_Q=k_Q,
        electrometer_calibration_factor=electrometer_calibration_factor,
        k_pol=k_pol, k_s=k_s, temperature_C=temperature_C,
        pressure_hPa=pressure_hPa, k_other=k_other,
        R50_cm=R50_cm, nominal_energy_MeV=nominal_energy_MeV,
    )
    result = calculate_dose_to_water_electron(inp)
    return templates.TemplateResponse(
        request=request, name="electron.html",
        context={"result": result, "inputs": inp, "detectors": list_detectors(), "beams": list_beams(modality="electron")},
    )


# -------------------- Brachy entry --------------------

@app.get("/brachy-select", response_class=HTMLResponse)
async def brachy_select(request: Request):
    # For now redirect to the existing brachy form; later we can add afterloader selection
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
    raw_reading: float = Form(...),
    N_SK: float = Form(...),
    electrometer_calibration_factor: float = Form(1.0),
    temperature_C: float = Form(20.0),
    pressure_hPa: float = Form(1013.25),
    k_ion: float = Form(1.0),
    k_other: float = Form(1.0),
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

@app.post("/linacs/{linac_id}/edit")
async def linac_edit(
    linac_id: str, name: str = Form(...), manufacturer: str = Form(""),
    model: str = Form(""), serial_number: str = Form(""), location: str = Form(""), notes: str = Form(""),
):
    update_linac(linac_id, name=name, manufacturer=manufacturer, model=model,
                 serial_number=serial_number, location=location, notes=notes)
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


# -------------------- Health --------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.9.0",
        "detectors": len(list_detectors()),
        "linacs": len(list_linacs()),
        "beams": len(list_beams()),
        "tolerances": len(list_tolerances()),
        "output_records": len(list_output_records()),
    }
