"""
TRS-398 Dosimetry App - FastAPI entry point
Final version (Stages 1-7)
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional, List

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
from app.chambers import (
    Chamber,
    add_chamber,
    get_chamber,
    list_chambers,
    delete_chamber,
    seed_example_chambers,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Absolute dosimetry for photons, electrons and brachytherapy (IAEA TRS-398)",
    version="0.7.0",
)

templates = Jinja2Templates(directory="app/templates")

# Seed example chambers on startup (in-memory)
seed_example_chambers()


# -------------------- Pydantic models --------------------

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


class ChamberCreate(BaseModel):
    id: str
    name: str
    type: str
    serial_number: str
    N_Dw: float
    calibration_quality: str = "Co-60"
    calibration_date: Optional[str] = None
    calibration_lab: Optional[str] = None
    notes: str = ""


# -------------------- Routes --------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stage": 7},
    )


@app.get("/photon", response_class=HTMLResponse)
async def photon_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="photon.html",
        context={"result": None},
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
        context={"result": result, "inputs": inp},
    )


@app.get("/electron", response_class=HTMLResponse)
async def electron_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="electron.html",
        context={"result": None},
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
        context={"result": result, "inputs": inp},
    )


@app.get("/brachy", response_class=HTMLResponse)
async def brachy_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="brachy.html",
        context={"result": None},
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
        context={"result": result, "inputs": inp},
    )


# ----- Chamber registry API (simple) -----

@app.get("/api/chambers")
async def api_list_chambers():
    return [asdict_chamber(c) for c in list_chambers()]


@app.post("/api/chambers")
async def api_add_chamber(data: ChamberCreate):
    if get_chamber(data.id):
        raise HTTPException(status_code=400, detail="Chamber ID already exists")
    ch = Chamber(**data.model_dump())
    add_chamber(ch)
    return asdict_chamber(ch)


@app.get("/api/chambers/{chamber_id}")
async def api_get_chamber(chamber_id: str):
    ch = get_chamber(chamber_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chamber not found")
    return asdict_chamber(ch)


@app.delete("/api/chambers/{chamber_id}")
async def api_delete_chamber(chamber_id: str):
    if not delete_chamber(chamber_id):
        raise HTTPException(status_code=404, detail="Chamber not found")
    return {"status": "deleted"}


def asdict_chamber(c: Chamber) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type,
        "serial_number": c.serial_number,
        "N_Dw": c.N_Dw,
        "calibration_quality": c.calibration_quality,
        "calibration_date": c.calibration_date,
        "calibration_lab": c.calibration_lab,
        "notes": c.notes,
    }


# ----- Calculation APIs -----

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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "stage": 7,
        "modules": ["photon", "electron", "brachy", "chambers"],
        "version": "0.7.0",
    }
