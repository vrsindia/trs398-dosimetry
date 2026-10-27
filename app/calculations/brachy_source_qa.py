"""HDR Brachytherapy Source QA calculations (AERB-style worksheets).

Implements formulas used in typical vendor/source commissioning sheets:
  2.5/2.6  Source transit time (TON/TOFF)
  4.3.1    Timer error
  4.3.2    Timer linearity & end error
  Decay    Manual vs TPS decay factor
  5.2.5    Single-source TG-43 vs TPS treatment time
  5.2.6    Multi-source TG-43 vs TPS treatment time
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

# Ir-192 half-life (days) — commonly used for HDR
IR192_HALF_LIFE_DAYS = 73.83

# Nucletron / Elekta mHDR-v2 typical constants (as in user sheet)
DEFAULT_DOSE_RATE_CONSTANT = 1.1121  # cGy h^-1 U^-1
DEFAULT_AIR_KERMA_RATE_CONST = 4.082  # cGy cm^2 h^-1 mCi^-1  (approx conversion path)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s or not str(s).strip():
        return None
    s = str(s).strip().replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def days_between(t0: str, t1: str) -> Optional[float]:
    d0, d1 = _parse_dt(t0), _parse_dt(t1)
    if not d0 or not d1:
        return None
    return (d1 - d0).total_seconds() / 86400.0


def decay_factor_ir192(days: float, half_life_days: float = IR192_HALF_LIFE_DAYS) -> float:
    if half_life_days <= 0:
        return 1.0
    return math.exp(-math.log(2) * days / half_life_days)


# ---------------------------------------------------------------------------
# 2.5 / 2.6  Transit time
# ---------------------------------------------------------------------------

def ton_toff(secondary_time_s: float, dwell_time_s: float) -> float:
    """TON/TOFF (sec) = (Secondary Time - Dwell Time) / 2"""
    return (float(secondary_time_s) - float(dwell_time_s)) / 2.0


# ---------------------------------------------------------------------------
# 4.3.1 Timer error
# ---------------------------------------------------------------------------

def timer_error_sec(
    R1: float,
    R2: float,
    dwell_time_s: float,
    n_interruptions: int = 1,
) -> float:
    """Timer error (s) = (R2 - R1) * t / ((n+1)*R1 - R2)

    R1 = charge without interruption
    R2 = charge with n interruptions during same programmed dwell t
    """
    t = float(dwell_time_s)
    n = int(n_interruptions)
    denom = (n + 1) * float(R1) - float(R2)
    if abs(denom) < 1e-15:
        raise ValueError("Denominator ((n+1)*R1 - R2) is zero")
    return (float(R2) - float(R1)) * t / denom


def timer_error_percent(timer_err_s: float, dwell_time_s: float) -> float:
    """% Timer error = (timer error in sec * 100) / dwell_time"""
    t = float(dwell_time_s)
    if abs(t) < 1e-15:
        raise ValueError("Dwell time is zero")
    return float(timer_err_s) * 100.0 / t


def average(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        raise ValueError("No values to average")
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# 4.3.2 Timer linearity & end error
# ---------------------------------------------------------------------------

def timer_linearity(
    times_s: Sequence[float],
    charges: Sequence[float],
) -> dict:
    """Linear fit Charge = a * Time + b.

    End / transit contribution estimated from intercept b.
    Linearity residual as max |measured - fit| / fit * 100.
    """
    xs = [float(x) for x in times_s]
    ys = [float(y) for y in charges]
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("Need at least 2 matched time/charge pairs")

    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        raise ValueError("Degenerate linear fit")

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    residuals_pct = []
    fitted = []
    for x, y in zip(xs, ys):
        yhat = slope * x + intercept
        fitted.append(yhat)
        if abs(yhat) > 1e-15:
            residuals_pct.append(abs(y - yhat) / abs(yhat) * 100.0)
        else:
            residuals_pct.append(0.0)

    # End error estimate: intercept / slope ≈ equivalent extra time (s)
    end_error_s = (intercept / slope) if abs(slope) > 1e-15 else 0.0

    return {
        "slope": slope,
        "intercept": intercept,
        "end_error_s": end_error_s,
        "max_residual_percent": max(residuals_pct) if residuals_pct else 0.0,
        "fitted": fitted,
        "residuals_percent": residuals_pct,
    }


# ---------------------------------------------------------------------------
# Decay factor check (manual vs TPS)
# ---------------------------------------------------------------------------

def decay_check(
    calib_dt: str,
    qa_dt: str,
    tps_decay_factor: float,
    half_life_days: float = IR192_HALF_LIFE_DAYS,
) -> dict:
    days = days_between(calib_dt, qa_dt)
    if days is None:
        raise ValueError("Could not parse calibration / QA date-time")
    manual = decay_factor_ir192(days, half_life_days)
    tps = float(tps_decay_factor)
    if abs(manual) < 1e-15:
        pct = 0.0
    else:
        pct = (tps - manual) / manual * 100.0
    return {
        "day_difference": days,
        "decay_factor_manual": manual,
        "decay_factor_tps": tps,
        "percent_deviation": pct,
    }


# ---------------------------------------------------------------------------
# 5.2.5 Single-source TG-43 treatment time vs TPS
# ---------------------------------------------------------------------------

def apparent_activity_at_qa(
    activity_mci_calib: float,
    calib_dt: str,
    qa_dt: str,
    half_life_days: float = IR192_HALF_LIFE_DAYS,
) -> dict:
    days = days_between(calib_dt, qa_dt)
    if days is None:
        raise ValueError("Could not parse dates")
    df = decay_factor_ir192(days, half_life_days)
    act = float(activity_mci_calib) * df
    return {"day_difference": days, "decay_factor": df, "activity_mci": act}


def single_source_treatment_time(
    activity_mci_at_qa: float,
    air_kerma_rate_const: float = DEFAULT_AIR_KERMA_RATE_CONST,
    dose_rate_constant: float = DEFAULT_DOSE_RATE_CONSTANT,
    g_r: float = 1.0,
    G_ratio: float = 1.0,
    F: float = 1.0,
    prescription_cgy: float = 1000.0,
    tps_time_s: Optional[float] = None,
) -> dict:
    """TG-43 at reference point (typically 1 cm transverse).

    S_K (U) path used in sheet:
      Air-kerma strength ≈ activity_mCi * air_kerma_rate_const   (µGy m^2 / h style scaling
      as used in the worksheet: numerical product matching their spreadsheet)

    Dose-rate (cGy/h) = S_K * Λ * g(r) * G_ratio * F
    Treatment time (h) = Dose / Dose-rate
    """
    sk = float(activity_mci_at_qa) * float(air_kerma_rate_const)
    # Sheet stores S_K numerically then multiplies Λ etc.
    # Their single-source block used S_K in µGym2/h and Λ=1.1121 → dose-rate cGy/h
    dose_rate = sk * float(dose_rate_constant) * float(g_r) * float(G_ratio) * float(F)
    if abs(dose_rate) < 1e-15:
        raise ValueError("Dose-rate is zero")
    t_h = float(prescription_cgy) / dose_rate
    t_s = t_h * 3600.0
    out = {
        "air_kerma_strength": sk,
        "dose_rate_cgy_per_h": dose_rate,
        "treatment_time_h": t_h,
        "treatment_time_s": t_s,
        "prescription_cgy": float(prescription_cgy),
    }
    if tps_time_s is not None:
        tps = float(tps_time_s)
        out["tps_time_s"] = tps
        out["percent_deviation"] = (tps - t_s) / t_s * 100.0 if abs(t_s) > 1e-15 else 0.0
    return out


# ---------------------------------------------------------------------------
# 5.2.6 Multi-source (3 positions, 1 cm spacing, Rx at 1 cm from centre)
# ---------------------------------------------------------------------------

@dataclass
class SourcePointContribution:
    distance_mm: float
    theta_deg: float
    g_r: float
    G: float
    F: float
    dose_rate_cgy_per_h: float


def geometry_factor_inverse_square(r_cm: float) -> float:
    """When r >> active length, G ≈ 1/r^2 relative to reference (sheet note)."""
    if abs(r_cm) < 1e-15:
        raise ValueError("r is zero")
    # Sheet uses G(r,θ)/G(r0,θ0) with r0=1 cm → (1/r)^2 for point approx at large r
    return 1.0 / (r_cm * r_cm)


def multi_source_treatment_time(
    activity_mci_at_qa: float,
    air_kerma_rate_const: float = DEFAULT_AIR_KERMA_RATE_CONST,
    dose_rate_constant: float = DEFAULT_DOSE_RATE_CONSTANT,
    # three sources: ends at 14.14 mm, centre at 10 mm (default geometry from sheet)
    distances_mm: Sequence[float] = (14.14, 10.0, 14.14),
    g_values: Sequence[float] = (1.002284, 1.0, 1.002284),
    G_values: Sequence[float] = (0.500151045615776, 1.0, 0.500151045615776),
    F_values: Sequence[float] = (0.9613, 1.0, 0.960914),
    prescription_cgy: float = 1000.0,
    tps_time_s: Optional[float] = None,
) -> dict:
    sk = float(activity_mci_at_qa) * float(air_kerma_rate_const)
    contribs = []
    total = 0.0
    for r_mm, g, G, F in zip(distances_mm, g_values, G_values, F_values):
        # Match sheet: dose-rate = S_K * Λ * g * G * F  with G already relative
        dr = sk * float(dose_rate_constant) * float(g) * float(G) * float(F)
        # Note: for centre point sheet reports ~45193 cGy/h with G=1; for ends G~0.5
        # Their end dose-rates were ~21778 — consistent with product above when units align.
        contribs.append(
            {
                "distance_mm": float(r_mm),
                "g_r": float(g),
                "G": float(G),
                "F": float(F),
                "dose_rate_cgy_per_h": dr,
            }
        )
        total += dr

    if abs(total) < 1e-15:
        raise ValueError("Total dose-rate is zero")
    t_h = float(prescription_cgy) / total
    t_s = t_h * 3600.0
    out = {
        "air_kerma_strength": sk,
        "contributions": contribs,
        "total_dose_rate_cgy_per_h": total,
        "treatment_time_h": t_h,
        "treatment_time_s": t_s,
        "prescription_cgy": float(prescription_cgy),
    }
    if tps_time_s is not None:
        tps = float(tps_time_s)
        out["tps_time_s"] = tps
        out["percent_deviation"] = (tps - t_s) / t_s * 100.0 if abs(t_s) > 1e-15 else 0.0
    return out


# ---------------------------------------------------------------------------
# Pass / fail helpers
# ---------------------------------------------------------------------------

def within_tolerance(value: float, limit: float) -> bool:
    return abs(float(value)) <= abs(float(limit))


def status_label(ok: bool) -> str:
    return "PASS" if ok else "FAIL"
