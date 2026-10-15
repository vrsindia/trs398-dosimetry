"""
TRS-398 Dosimetry App - FastAPI entry point
Stages 1-2: Skeleton + Photon calculation UI & API
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional

from app.calculations.photon import (
    PhotonMeasurementInput,
    calculate_dose_to_water_photon,
    calculate_k_TP,
    calculate_k_pol,
    calculate_k_s_two_voltage,
)

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Absolute dosimetry for photons, electrons and brachytherapy (IAEA TRS-398)",
    version="0.2.0",
)

templates = Jinja2Templates(directory="app/templates")


# -------------------- Pydantic models for API --------------------

class PhotonCalcRequest(BaseModel):
    raw_charge_nC: float = Field(..., gt=0, description="Measured charge in nC")
    N_Dw: float = Field(..., gt=0, description="Calibration coefficient N_D,w (Gy/nC)")
    k_Q: float = Field(..., gt=0, description="Beam quality correction factor")
    electrometer_calibration_factor: float = Field(1.0, gt=0)
    k_pol: float = Field(1.0, gt=0)
    k_s: float = Field(1.0, gt=0)
    temperature_C: float = Field(20.0)
    pressure_hPa: float = Field(1013.25, gt=0)
    k_other: float = Field(1.0, gt=0)


class PhotonCalcResponse(BaseModel):
    dose_to_water_Gy: float
    M_Q_corrected: float
    k_TP: float
    factors_used: dict


# -------------------- Routes --------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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


@app.post("/api/photon", response_model=PhotonCalcResponse)
async def api_photon_calculate(data: PhotonCalcRequest):
    inp = PhotonMeasurementInput(**data.model_dump())
    result = calculate_dose_to_water_photon(inp)
    return PhotonCalcResponse(
        dose_to_water_Gy=result.dose_to_water_Gy,
        M_Q_corrected=result.M_Q_corrected,
        k_TP=result.k_TP,
        factors_used=result.factors_used,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "stage": 2,
        "modules": ["photon"],
        "version": "0.2.0",
    }
