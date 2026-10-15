"""
TRS-398 Absolute Dosimetry – High Energy Photon Beams

Implements the core formula from IAEA TRS-398:

    Dw = M_Q * N_D,w * k_Q * k_pol * k_s * k_TP * ...

All functions are pure (no side effects) and fully typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True)
class PhotonMeasurementInput:
    """Raw measurement data + chamber calibration data."""

    # Required fields first (no defaults)
    raw_charge_nC: float
    N_Dw: float
    k_Q: float

    # Optional fields with defaults
    electrometer_calibration_factor: float = 1.0
    k_pol: float = 1.0
    k_s: float = 1.0
    temperature_C: float = 20.0
    pressure_hPa: float = 1013.25
    T0_C: float = 20.0
    P0_hPa: float = 1013.25
    k_other: float = 1.0


@dataclass(frozen=True)
class PhotonDoseResult:
    """Result of TRS-398 photon absolute dose calculation."""

    dose_to_water_Gy: float
    M_Q_corrected: float
    k_TP: float
    factors_used: dict


def calculate_k_TP(temperature_C: float, pressure_hPa: float,
                   T0_C: float = 20.0, P0_hPa: float = 1013.25) -> float:
    """
    Temperature-pressure correction factor according to TRS-398.

    k_TP = (273.15 + T) / (273.15 + T0) * (P0 / P)
    """
    return ((273.15 + temperature_C) / (273.15 + T0_C)) * (P0_hPa / pressure_hPa)


def calculate_k_pol(M_plus: float, M_minus: float) -> float:
    """
    Polarity correction factor.

    k_pol = (|M+| + |M-|) / (2 * M)
    where M is the reading with the polarity used for the dose determination.
    """
    if M_plus == 0 and M_minus == 0:
        raise ValueError("Both polarity readings cannot be zero")
    return (abs(M_plus) + abs(M_minus)) / (2.0 * abs(M_plus))


def calculate_k_s_two_voltage(M1: float, M2: float, V1: float, V2: float,
                              beam_type: str = "pulsed") -> float:
    """
    Ion recombination correction using the two-voltage method (TRS-398).
    """
    if V1 <= V2:
        raise ValueError("V1 must be the higher voltage")

    ratio = M1 / M2
    voltage_ratio = V1 / V2

    if beam_type.lower() == "pulsed":
        ks = (voltage_ratio - 1) / (voltage_ratio - ratio)
    else:
        ks = (voltage_ratio**2 - 1) / (voltage_ratio**2 - ratio)

    return ks


def calculate_dose_to_water_photon(inp: PhotonMeasurementInput) -> PhotonDoseResult:
    """
    Main TRS-398 calculation for high-energy photon beams.

    Dw (Gy) = M_Q * N_D,w * k_Q * k_pol * k_s * k_TP * k_other
    """

    k_TP = calculate_k_TP(
        temperature_C=inp.temperature_C,
        pressure_hPa=inp.pressure_hPa,
        T0_C=inp.T0_C,
        P0_hPa=inp.P0_hPa,
    )

    M_Q = (
        inp.raw_charge_nC
        * inp.electrometer_calibration_factor
        * inp.k_pol
        * inp.k_s
        * k_TP
        * inp.k_other
    )

    dose_Gy = M_Q * inp.N_Dw * inp.k_Q

    factors = {
        "raw_charge_nC": inp.raw_charge_nC,
        "electrometer_factor": inp.electrometer_calibration_factor,
        "N_Dw": inp.N_Dw,
        "k_Q": inp.k_Q,
        "k_pol": inp.k_pol,
        "k_s": inp.k_s,
        "k_TP": round(k_TP, 6),
        "k_other": inp.k_other,
        "M_Q_corrected": round(M_Q, 6),
    }

    return PhotonDoseResult(
        dose_to_water_Gy=dose_Gy,
        M_Q_corrected=M_Q,
        k_TP=k_TP,
        factors_used=factors,
    )
