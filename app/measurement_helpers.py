"""Apply calc profile factors and average readings."""

from __future__ import annotations
from typing import List, Optional, Tuple
from app.models import CalcProfile, get_default_calc_profile
from app.calculations.photon import PhotonMeasurementInput, calculate_dose_to_water_photon
from app.session import SessionCorrectionFactors


def effective_factors(corr: SessionCorrectionFactors, profile: Optional[CalcProfile],
                      k_Q: float, electrometer: float = 1.0) -> Tuple[float, float, float, float, float]:
    if profile is None:
        profile = get_default_calc_profile()
    use_k_TP = True if profile is None else profile.use_k_TP
    use_k_pol = True if profile is None else profile.use_k_pol
    use_k_s = True if profile is None else profile.use_k_s
    use_k_Q = True if profile is None else profile.use_k_Q
    use_elec = True if profile is None else profile.use_electrometer_factor
    k_TP = corr.k_TP if use_k_TP else 1.0
    k_pol = corr.k_pol if use_k_pol else 1.0
    k_s = corr.k_s if use_k_s else 1.0
    k_Q_eff = k_Q if use_k_Q else 1.0
    elec = electrometer if use_elec else 1.0
    return k_TP, k_pol, k_s, k_Q_eff, elec


def compute_output(readings: List[float], mu: float, N_Dw: float, k_Q: float,
                   corr: SessionCorrectionFactors, profile: Optional[CalcProfile] = None) -> dict:
    if not readings:
        raise ValueError("No readings")
    avg = float(sum(readings) / len(readings))
    mu = float(mu) if mu else 100.0
    N_Dw = float(N_Dw)
    k_Q = float(k_Q)
    k_TP, k_pol, k_s, k_Q_eff, elec = effective_factors(corr, profile, k_Q)
    t_c = getattr(corr, "temperature_C", 20.0) or 20.0
    p_h = getattr(corr, "pressure_hPa", 1013.25) or 1013.25
    if profile is not None and not profile.use_k_TP:
        t_c, p_h = 20.0, 1013.25
    inp = PhotonMeasurementInput(
        raw_charge_nC=avg,
        N_Dw=N_Dw,
        k_Q=k_Q_eff,
        electrometer_calibration_factor=elec,
        k_pol=k_pol,
        k_s=k_s,
        temperature_C=t_c,
        pressure_hPa=p_h,
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
