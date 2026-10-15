"""
Brachytherapy Source Strength Determination

Well-type ionization chamber measurements for HDR/PDR/LDR sources.
Primary quantity: Air Kerma Strength (S_K) or Reference Air Kerma Rate (RAKR).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone
import math


# Approximate half-lives (days) for common sources – for decay correction
HALF_LIVES_DAYS = {
    "Ir-192": 73.827,
    "Co-60": 1925.28,          # ~5.27 years
    "Cs-137": 11018.3,         # ~30.17 years
    "I-125": 59.49,
    "Pd-103": 16.991,
}


@dataclass(frozen=True)
class BrachyWellInput:
    """Input data for well-chamber source strength measurement."""

    # Measured charge or current
    raw_reading: float                  # nC or nA depending on mode
    electrometer_calibration_factor: float = 1.0

    # Well-chamber calibration coefficient (Gy m² h⁻¹ / A or equivalent)
    # Common unit: µGy m² h⁻¹ / nA  or  cGy cm² h⁻¹ / A
    N_SK: float                         # calibration factor for air kerma strength

    # Environmental conditions
    temperature_C: float = 20.0
    pressure_hPa: float = 1013.25
    T0_C: float = 20.0
    P0_hPa: float = 1013.25

    # Optional corrections
    k_ion: float = 1.0                  # recombination / collection efficiency
    k_other: float = 1.0

    # Source information for decay correction
    nuclide: str = "Ir-192"
    calibration_datetime: Optional[str] = None   # ISO format of source calibration
    measurement_datetime: Optional[str] = None   # ISO format of this measurement

    # Integration time if charge mode (seconds)
    integration_time_s: Optional[float] = None


@dataclass(frozen=True)
class BrachyWellResult:
    air_kerma_strength: float           # S_K in the unit of N_SK
    decay_factor: float
    k_TP: float
    factors_used: dict


def calculate_k_TP(temperature_C: float, pressure_hPa: float,
                   T0_C: float = 20.0, P0_hPa: float = 1013.25) -> float:
    return ((273.15 + temperature_C) / (273.15 + T0_C)) * (P0_hPa / pressure_hPa)


def decay_factor(nuclide: str, t_calib: Optional[str], t_meas: Optional[str]) -> float:
    """
    Calculate decay factor from calibration date to measurement date.
    Returns 1.0 if dates are missing.
    """
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

    S_K = M * N_SK * k_TP * k_ion * k_other * decay_factor

    where M is the corrected electrometer reading (current or charge/time).
    """

    k_TP = calculate_k_TP(
        temperature_C=inp.temperature_C,
        pressure_hPa=inp.pressure_hPa,
        T0_C=inp.T0_C,
        P0_hPa=inp.P0_hPa,
    )

    # If charge mode, convert to current-like quantity
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
