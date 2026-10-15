"""
TRS-398 Dosimetry App - FastAPI entry point
With Detector, Linac and Beam libraries
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

from app.calculations.photon import (
    PhotonMeasurementInput,
    calculate_dose_to_water_photon,
)
from app.calculations.electron import (
    ElectronMeasurementInput,
    calculate_dose_to_water_electron,
)
from app.calculations.brachy import (
    BrachyWellInput,
    calculate_air_kerma_strength,
)
from app.models import (
    Detector, Linac, Beam,
    add_detector, get_detector, list_detectors, update_detector, delete_detector,
    add_linac, get_linac, list_linacs, update_linac, delete_linac,
    add_beam, get_beam, list_beams, update_beam, delete_beam,
    seed_libraries, _new_id,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Absolute dosimetry for photons, electrons and brachytherapy (IAEA TRS-398)",
    version="0.8.0",
)

templates = Jinja2Templates(directory="app/templates")

# Seed example data on startup
seed_libraries()


# -------------------- Pydantic models for calculation APIs --------------------

class PhotonCalcRequest(BaseModel):
    raw_charge_nC: float = Field(..., gt=0)
    N_Dw: float = Field(..., gt=0)
    k_Q: float = Field(..., gt=0)
    electrometer_calibration_factor: float = Field(1.0, gt=0)
    k_pol: float = Field(1.0, gt=0)
    k_s: float = Field(1.0, gt=0)
    temperature_C: float = Field(20.0)
    pressure_hPa: float = Field(1013.25, gt=0)
    k_other: float = Field(1.0, gt=0)


class ElectronCalcRequest(BaseModel):
    raw_charge_nC: float = Field(..., gt=0)
    N_Dw: float = Field(..., gt=0)
    k_Q: float = Field(..., gt=0)
    electrometer_calibration_factor: float = Field(1.0, gt=0)
    k_pol: float = Field(1.0, gt=0)
    k_s: float = Field(1.0, gt=0)
    temperature_C: float = Field(20.0)
    pressure_hPa: float = Field(1013.25, gt=0)
    k_other: float = Field(1.0, gt=0)
    R50_cm: Optional[float] = None
    nominal_energy_MeV: Optional[float] = None


class BrachyCalcRequest(BaseModel):
    raw_reading: float
    N_SK: float = Field(..., gt=0)
    electrometer_calibration_factor: float = Field(1.0, gt=0)
    temperature_C: float = Field(20.0)
    pressure_hPa: float = Field(1013.25, gt=0)
    k_ion: float = Field(1.0, gt=0)
    k_other: float = Field(1.0, gt=0)
    nuclide: str = Field("Ir-192")
    calibration_datetime: Optional[str] = None
    measurement_datetime: Optional[str] = None
    integration_time_s: Optional[float] = None


# -------------------- Home & Calculation pages --------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "detectors": list_detectors(),
            "linacs": list_linacs(),
        },
    )


@app.get("/photon", response_class=HTMLResponse)
async def photon_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="photon.html",
        context={
            "result": None,
            "detectors": list_detectors(),
            "linacs": list_linacs(),
            "beams": list_beams(),
        },
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
        raw_charge_nC=raw_charge_nC,
        N_Dw=N_Dw,
        k_Q=k_Q,
        electrometer_calibration_factor=electrometer_calibration_factor,
        k_pol=k_pol,
        k_s=k_s,
        temperature_C=temperature_C,
        pressure_hPa=pressure_hPa,
        k_other=k_other,
    )
    result = calculate_dose_to_water_photon(inp)
    return templates.TemplateResponse(
        request=request,
        name="photon.html",
        context={
            "result": result,
            "inputs": inp,
            "detectors": list_detectors(),
            "linacs": list_linacs(),
            "beams": list_beams(),
        },
    )


@app.get("/electron", response_class=HTMLResponse)
async def electron_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="electron.html",
        context={
            "result": None,
            "detectors": list_detectors(),
            "linacs": list_linacs(),
            "beams": list_beams(),
        },
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
        raw_charge_nC=raw_charge_nC,
        N_Dw=N_Dw,
        k_Q=k_Q,
        electrometer_calibration_factor=electrometer_calibration_factor,
        k_pol=k_pol,
        k_s=k_s,
        temperature_C=temperature_C,
        pressure_hPa=pressure_hPa,
        k_other=k_other,
        R50_cm=R50_cm,
        nominal_energy_MeV=nominal_energy_MeV,
    )
    result = calculate_dose_to_water_electron(inp)
    return templates.TemplateResponse(
        request=request,
        name="electron.html",
        context={
            "result": result,
            "inputs": inp,
            "detectors": list_detectors(),
            "linacs": list_linacs(),
            "beams": list_beams(),
        },
    )


@app.get("/brachy", response_class=HTMLResponse)
async def brachy_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="brachy.html",
        context={
            "result": None,
            "detectors": list_detectors(),
        },
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
        raw_reading=raw_reading,
        N_SK=N_SK,
        electrometer_calibration_factor=electrometer_calibration_factor,
        temperature_C=temperature_C,
        pressure_hPa=pressure_hPa,
        k_ion=k_ion,
        k_other=k_other,
        nuclide=nuclide,
        calibration_datetime=calibration_datetime or None,
        measurement_datetime=measurement_datetime or None,
        integration_time_s=integration_time_s,
    )
    result = calculate_air_kerma_strength(inp)
    return templates.TemplateResponse(
        request=request,
        name="brachy.html",
        context={
            "result": result,
            "inputs": inp,
            "detectors": list_detectors(),
        },
    )


# -------------------- Detector Library Management --------------------

@app.get("/detectors", response_class=HTMLResponse)
async def detectors_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="detectors.html",
        context={"detectors": list_detectors()},
    )


@app.post("/detectors/add")
async def detector_add(
    name: str = Form(...),
    detector_type: str = Form(...),
    serial_number: str = Form(...),
    calibration_factor: float = Form(...),
    calibration_quality: str = Form("Co-60"),
    calibration_date: str = Form(""),
    calibration_lab: str = Form(""),
    next_due_date: str = Form(""),
    notes: str = Form(""),
    unit: str = Form("Gy/nC"),
):
    det = Detector(
        id=_new_id(),
        name=name,
        detector_type=detector_type,
        serial_number=serial_number,
        calibration_factor=calibration_factor,
        calibration_quality=calibration_quality,
        calibration_date=calibration_date or None,
        calibration_lab=calibration_lab or None,
        next_due_date=next_due_date or None,
        notes=notes,
        unit=unit,
    )
    add_detector(det)
    return RedirectResponse(url="/detectors", status_code=303)


@app.post("/detectors/{det_id}/edit")
async def detector_edit(
    det_id: str,
    name: str = Form(...),
    detector_type: str = Form(...),
    serial_number: str = Form(...),
    calibration_factor: float = Form(...),
    calibration_quality: str = Form("Co-60"),
    calibration_date: str = Form(""),
    calibration_lab: str = Form(""),
    next_due_date: str = Form(""),
    notes: str = Form(""),
    unit: str = Form("Gy/nC"),
):
    update_detector(
        det_id,
        name=name,
        detector_type=detector_type,
        serial_number=serial_number,
        calibration_factor=calibration_factor,
        calibration_quality=calibration_quality,
        calibration_date=calibration_date or None,
        calibration_lab=calibration_lab or None,
        next_due_date=next_due_date or None,
        notes=notes,
        unit=unit,
    )
    return RedirectResponse(url="/detectors", status_code=303)


@app.post("/detectors/{det_id}/delete")
async def detector_delete(det_id: str):
    delete_detector(det_id)
    return RedirectResponse(url="/detectors", status_code=303)


# -------------------- Linac Library Management --------------------

@app.get("/linacs", response_class=HTMLResponse)
async def linacs_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="linacs.html",
        context={
            "linacs": list_linacs(),
            "beams": list_beams(),
        },
    )


@app.post("/linacs/add")
async def linac_add(
    name: str = Form(...),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_number: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
):
    linac = Linac(
        id=_new_id(),
        name=name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        location=location,
        notes=notes,
    )
    add_linac(linac)
    return RedirectResponse(url="/linacs", status_code=303)


@app.post("/linacs/{linac_id}/edit")
async def linac_edit(
    linac_id: str,
    name: str = Form(...),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_number: str = Form(""),
    location: str = Form(""),
    notes: str = Form(""),
):
    update_linac(
        linac_id,
        name=name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        location=location,
        notes=notes,
    )
    return RedirectResponse(url="/linacs", status_code=303)


@app.post("/linacs/{linac_id}/delete")
async def linac_delete(linac_id: str):
    delete_linac(linac_id)
    return RedirectResponse(url="/linacs", status_code=303)


# -------------------- Beam / Energy Management --------------------

@app.post("/beams/add")
async def beam_add(
    linac_id: str = Form(...),
    modality: str = Form(...),
    nominal_energy: str = Form(...),
    measurement_depth_cm: float = Form(...),
    pdd: float = Form(...),
    k_Q: float = Form(...),
    ssd_cm: float = Form(100.0),
    field_size: str = Form("10x10"),
    notes: str = Form(""),
):
    beam = Beam(
        id=_new_id(),
        linac_id=linac_id,
        modality=modality,
        nominal_energy=nominal_energy,
        measurement_depth_cm=measurement_depth_cm,
        pdd=pdd,
        k_Q=k_Q,
        ssd_cm=ssd_cm,
        field_size=field_size,
        notes=notes,
    )
    add_beam(beam)
    return RedirectResponse(url="/linacs", status_code=303)


@app.post("/beams/{beam_id}/delete")
async def beam_delete(beam_id: str):
    delete_beam(beam_id)
    return RedirectResponse(url="/linacs", status_code=303)


# -------------------- API endpoints (kept for programmatic use) --------------------

@app.post("/api/photon")
async def api_photon_calculate(data: PhotonCalcRequest):
    inp = PhotonMeasurementInput(**data.model_dump())
    result = calculate_dose_to_water_photon(inp)
    return {
        "dose_to_water_Gy": result.dose_to_water_Gy,
        "M_Q_corrected": result.M_Q_corrected,
        "k_TP": result.k_TP,
        "factors_used": result.factors_used,
    }


@app.post("/api/electron")
async def api_electron_calculate(data: ElectronCalcRequest):
    inp = ElectronMeasurementInput(**data.model_dump())
    result = calculate_dose_to_water_electron(inp)
    return {
        "dose_to_water_Gy": result.dose_to_water_Gy,
        "M_Q_corrected": result.M_Q_corrected,
        "k_TP": result.k_TP,
        "factors_used": result.factors_used,
    }


@app.post("/api/brachy")
async def api_brachy_calculate(data: BrachyCalcRequest):
    inp = BrachyWellInput(**data.model_dump())
    result = calculate_air_kerma_strength(inp)
    return {
        "air_kerma_strength": result.air_kerma_strength,
        "decay_factor": result.decay_factor,
        "k_TP": result.k_TP,
        "factors_used": result.factors_used,
    }


@app.get("/api/detectors")
async def api_list_detectors():
    return [d.__dict__ for d in list_detectors()]


@app.get("/api/linacs")
async def api_list_linacs():
    return [l.__dict__ for l in list_linacs()]


@app.get("/api/beams")
async def api_list_beams(linac_id: Optional[str] = None):
    return [b.__dict__ for b in list_beams(linac_id)]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.8.0",
        "modules": ["photon", "electron", "brachy", "detectors", "linacs", "beams"],
        "detectors": len(list_detectors()),
        "linacs": len(list_linacs()),
        "beams": len(list_beams()),
    }
