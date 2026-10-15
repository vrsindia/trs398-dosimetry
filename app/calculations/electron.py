"""
TRS-398 Absolute Dosimetry – High Energy Electron Beams

Implements the core formalism from IAEA TRS-398 for electron beams.
Uses parallel-plate or cylindrical chambers with appropriate k_Q / k_Q,Qo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .photon import calculate_k_TP  # reuse the same k_TP function


@dataclass(frozen=True)
class ElectronMeasurementInput:
    """Raw measurement data + chamber calibration data for electrons."""

    raw_charge_nC: float
    electrometer_calibration_factor: float = 1.0

    # N_D,w at the calibration quality (usually Co-60)
    N_Dw: float

    # Beam quality correction factor for the electron beam
    k_Q: float

    k_pol: float = 1.0
    k_s: float = 1.0

    temperature_C: float = 20.0
    pressure_hPa: float = 1013.25
    T0_C: float = 20.0
    P0_hPa: float = 1013.25

    k_other: float = 1.0

    # Optional: nominal energy / R50 for documentation
    R50_cm: Optional[float] = None
    nominal_energy_MeV: Optional[float] = None


@dataclass(frozen=True)
class ElectronDoseResult:
    dose_to_water_Gy: float
    M_Q_corrected: float
    k_TP: float
    factors_used: dict


def calculate_dose_to_water_electron(inp: ElectronMeasurementInput) -> ElectronDoseResult:
    """
    Main TRS-398 calculation for high-energy electron beams.

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
        "R50_cm": inp.R50_cm,
        "nominal_energy_MeV": inp.nominal_energy_MeV,
    }

    return ElectronDoseResult(
        dose_to_water_Gy=dose_Gy,
        M_Q_corrected=M_Q,
        k_TP=k_TP,
        factors_used=factors,
    )
