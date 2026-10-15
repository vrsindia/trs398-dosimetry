"""
TRS-398 Dosimetry App - FastAPI entry point
Stages 1-3: Photon + Electron absolute dosimetry
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional

from app.calculations.photon import (
    PhotonMeasurementInput,
    calculate_dose_to_water_photon,
)
from app.calculations.electron import (
    ElectronMeasurementInput,
    calculate_dose_to_water_electron,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Absolute dosimetry for photons, electrons and brachytherapy (IAEA TRS-398)",
    version="0.3.0",
)

templates = Jinja2Templates(directory="app/templates")


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


# -------------------- Routes --------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "stage": 3})


@app.get("/photon", response_class=HTMLResponse)
async def photon_form(request: Request):
    return templates.TemplateResponse("photon.html", {"request": request, "result": None})


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
        "photon.html",
        {"request": request, "result": result, "inputs": inp},
    )


@app.get("/electron", response_class=HTMLResponse)
async def electron_form(request: Request):
    return templates.TemplateResponse("electron.html", {"request": request, "result": None})


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
        "electron.html",
        {"request": request, "result": result, "inputs": inp},
    )


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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "stage": 3,
        "modules": ["photon", "electron"],
        "version": "0.3.0",
    }
