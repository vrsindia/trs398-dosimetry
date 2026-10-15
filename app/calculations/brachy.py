"""
Brachytherapy Source Strength Determination
Well-type ionization chamber measurements for HDR/PDR/LDR sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import math


HALF_LIVES_DAYS = {
    "Ir-192": 73.827,
    "Co-60": 1925.28,
    "Cs-137": 11018.3,
    "I-125": 59.49,
    "Pd-103": 16.991,
}


@dataclass(frozen=True)
class BrachyWellInput:
    """Input data for well-chamber source strength measurement."""

    # Required fields first
    raw_reading: float
    N_SK: float

    # Optional fields with defaults
    electrometer_calibration_factor: float = 1.0
    temperature_C: float = 20.0
    pressure_hPa: float = 1013.25
    T0_C: float = 20.0
    P0_hPa: float = 1013.25
    k_ion: float = 1.0
    k_other: float = 1.0
    nuclide: str = "Ir-192"
    calibration_datetime: Optional[str] = None
    measurement_datetime: Optional[str] = None
    integration_time_s: Optional[float] = None


@dataclass(frozen=True)
class BrachyWellResult:
    air_kerma_strength: float
    decay_factor: float
    k_TP: float
    factors_used: dict


def calculate_k_TP(temperature_C: float, pressure_hPa: float,
                   T0_C: float = 20.0, P0_hPa: float = 1013.25) -> float:
    return ((273.15 + temperature_C) / (273.15 + T0_C)) * (P0_hPa / pressure_hPa)


def decay_factor(nuclide: str, t_calib: Optional[str], t_meas: Optional[str]) -> float:
    if not t_calib or not t_meas:
        return 1.0

    try:
        dt_calib = datetime.fromisoformat(t_calib.replace("Z", "+00:00"))
        dt_meas = datetime.fromisoformat(t_meas.replace("Z", "+00:00"))
    except Exception:
        return 1.0

    half_life = HALF_LIVES_DAYS.get(nuclide)
    if not half_life:
        return 1.0

    delta_days = (dt_meas - dt_calib).total_seconds() / 86400.0
    return math.exp(-math.log(2) * delta_days / half_life)


def calculate_air_kerma_strength(inp: BrachyWellInput) -> BrachyWellResult:
    """
    Calculate Air Kerma Strength (S_K) from well-chamber reading.
    """

    k_TP = calculate_k_TP(
        temperature_C=inp.temperature_C,
        pressure_hPa=inp.pressure_hPa,
        T0_C=inp.T0_C,
        P0_hPa=inp.P0_hPa,
    )

    if inp.integration_time_s and inp.integration_time_s > 0:
        M = inp.raw_reading / inp.integration_time_s
    else:
        M = inp.raw_reading

    M_corrected = (
        M
        * inp.electrometer_calibration_factor
        * inp.k_ion
        * k_TP
        * inp.k_other
    )

    df = decay_factor(inp.nuclide, inp.calibration_datetime, inp.measurement_datetime)

    S_K = M_corrected * inp.N_SK * df

    factors = {
        "raw_reading": inp.raw_reading,
        "electrometer_factor": inp.electrometer_calibration_factor,
        "N_SK": inp.N_SK,
        "k_TP": round(k_TP, 6),
        "k_ion": inp.k_ion,
        "k_other": inp.k_other,
        "decay_factor": round(df, 6),
        "nuclide": inp.nuclide,
        "M_corrected": round(M_corrected, 6),
    }

    return BrachyWellResult(
        air_kerma_strength=S_K,
        decay_factor=df,
        k_TP=k_TP,
        factors_used=factors,
    )
