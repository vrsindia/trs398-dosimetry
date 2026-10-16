"""Apply calc profile factors and average readings."""

from __future__ import annotations
from typing import List, Optional, Tuple
from app.models import CalcProfile, get_default_calc_profile, get_calc_profile
from app.calculations.photon import PhotonMeasurementInput, calculate_dose_to_water_photon
from app.session import SessionCorrectionFactors


def effective_factors(corr: SessionCorrectionFactors, profile: Optional[CalcProfile],
                     k_Q: float, electrometer: float = 1.0) -> Tuple[float, float, float, float, float]:
    if profile is None:
        profile = get_default_calc_profile()
    k_TP = corr.k_TP if (not profile or profile.use_k_TP) else 1.0
    k_pol = corr.k_pol if (not profile or profile.use_k_pol) else 1.0
    k_s = corr.k_s if (not profile or profile.use_k_s) else 1.0
    k_Q_eff = k_Q if (not profile or profile.use_k_Q) else 1.0
    elec = electrometer if (not profile or profile.use_electrometer_factor) else 1.0
    return k_TP, k_pol, k_s, k_Q_eff, elec


def compute_output(readings: List[float], mu: float, N_Dw: float, k_Q: float,
                   corr: SessionCorrectionFactors, profile: Optional[CalcProfile] = None) -> dict:
    if not readings:
        raise ValueError("No readings")
    avg = sum(readings) / len(readings)
    k_TP, k_pol, k_s, k_Q_eff, elec = effective_factors(corr, profile, k_Q)
    inp = PhotonMeasurementInput(
        raw_charge_nC=avg, N_Dw=N_Dw, k_Q=k_Q_eff,
        electrometer_calibration_factor=elec,
        k_pol=k_pol, k_s=k_s,
        temperature_C=corr.temperature_C, pressure_hPa=corr.pressure_hPa,
    )
    # Bypass TP double-count: calculate_dose already applies k_TP from T/P
    # but we already folded profile into k_pol/k_s; k_TP from T/P is correct when use_k_TP
    if profile and not profile.use_k_TP:
        inp = PhotonMeasurementInput(
            raw_charge_nC=avg, N_Dw=N_Dw, k_Q=k_Q_eff,
            electrometer_calibration_factor=elec,
            k_pol=k_pol, k_s=k_s,
            temperature_C=20.0, pressure_hPa=1013.25,  # forces k_TP ~ 1
        )
    dr = calculate_dose_to_water_photon(inp)
    out = (dr.dose_to_water_Gy * 100.0) / mu if mu > 0 else 0.0
    return {
        "dose_Gy": dr.dose_to_water_Gy,
        "M_Q": dr.M_Q_corrected,
        "output_cGy_MU": out,
        "mu": mu,
        "avg_charge": avg,
        "n_readings": len(readings),
        "readings": readings,
        "last_charge": readings[-1],
        "N_Dw": N_Dw,
        "k_Q": k_Q_eff,
        "readings_json": ",".join(str(x) for x in readings),
    }
