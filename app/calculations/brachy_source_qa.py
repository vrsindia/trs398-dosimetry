"""HDR Brachytherapy Source QA calculations."""
from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional, Sequence

IR192_HALF_LIFE_DAYS = 73.83
DEFAULT_DOSE_RATE_CONSTANT = 1.1121
DEFAULT_AIR_KERMA_RATE_CONST = 4.082

# Source library (name -> half-life days)
SOURCE_HALF_LIVES = {
    "Ir-192": 73.83,
    "Co-60": 5.2714 * 365.25,
    "Cs-137": 30.17 * 365.25,
    "I-125": 59.4,
    "Pd-103": 16.99,
    "Ra-226": 1600 * 365.25,
    "Y-90": 2.67,
    "Sr-90": 28.8 * 365.25,
}


def list_sources() -> List[str]:
    return sorted(SOURCE_HALF_LIVES.keys())


def half_life_for_source(source_name: str) -> float:
    name = (source_name or "").strip()
    if name in SOURCE_HALF_LIVES:
        return SOURCE_HALF_LIVES[name]
    # aliases
    key = name.replace(" ", "").replace("_", "-").upper()
    aliases = {
        "IR192": "Ir-192", "IR-192": "Ir-192",
        "CO60": "Co-60", "CO-60": "Co-60",
        "CS137": "Cs-137", "I125": "I-125", "PD103": "Pd-103",
    }
    canon = aliases.get(key)
    if canon:
        return SOURCE_HALF_LIVES[canon]
    raise ValueError("Unknown source: %s" % source_name)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s or not str(s).strip():
        return None
    s = str(s).strip().replace("Z", "+00:00").replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(str(s).strip())
    except Exception:
        return None


def days_between(t0: str, t1: str) -> Optional[float]:
    d0, d1 = _parse_dt(t0), _parse_dt(t1)
    if not d0 or not d1:
        return None
    return (d1 - d0).total_seconds() / 86400.0


def decay_factor(days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    return math.exp(-math.log(2) * days / half_life_days)


def ton_toff(secondary_time_s: float, dwell_time_s: float) -> float:
    return (float(secondary_time_s) - float(dwell_time_s)) / 2.0


def ton_toff_multi(secondaries: Sequence[float], dwells: Sequence[float]) -> dict:
    if len(secondaries) != len(dwells) or not secondaries:
        raise ValueError("Need matching secondary and dwell times")
    values = [ton_toff(s, d) for s, d in zip(secondaries, dwells)]
    avg = sum(values) / len(values)
    return {"trials": values, "average": avg, "n": len(values)}


def timer_error_sec(R1: float, R2: float, dwell_time_s: float, n_interruptions: int = 1) -> float:
    t = float(dwell_time_s)
    n = int(n_interruptions)
    denom = (n + 1) * float(R1) - float(R2)
    if abs(denom) < 1e-15:
        raise ValueError("Denominator ((n+1)*R1 - R2) is zero")
    return (float(R2) - float(R1)) * t / denom


def timer_error_percent(timer_err_s: float, dwell_time_s: float) -> float:
    t = float(dwell_time_s)
    if abs(t) < 1e-15:
        raise ValueError("Dwell time is zero")
    return float(timer_err_s) * 100.0 / t


def average(values: Sequence[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        raise ValueError("No values to average")
    return sum(vals) / len(vals)


def timer_linearity(times_s: Sequence[float], charges: Sequence[float]) -> dict:
    xs = [float(x) for x in times_s]
    ys = [float(y) for y in charges]
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("Need at least 2 matched time/charge pairs")
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        raise ValueError("Degenerate linear fit")
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    residuals_pct, fitted = [], []
    for x, y in zip(xs, ys):
        yhat = slope * x + intercept
        fitted.append(yhat)
        residuals_pct.append(abs(y - yhat) / abs(yhat) * 100.0 if abs(yhat) > 1e-15 else 0.0)
    end_error_s = (intercept / slope) if abs(slope) > 1e-15 else 0.0
    return {
        "slope": slope,
        "intercept": intercept,
        "end_error_s": end_error_s,
        "max_residual_percent": max(residuals_pct) if residuals_pct else 0.0,
        "fitted": fitted,
        "residuals_percent": residuals_pct,
        "times": xs,
        "charges": ys,
    }


def decay_check(
    calib_dt: str,
    qa_dt: str,
    tps_decay_factor: float,
    source_name: str = "Ir-192",
) -> dict:
    days = days_between(calib_dt, qa_dt)
    if days is None:
        raise ValueError("Could not parse calibration / QA date-time")
    t_half = half_life_for_source(source_name)
    manual = decay_factor(days, t_half)
    tps = float(tps_decay_factor)
    pct = (tps - manual) / manual * 100.0 if abs(manual) > 1e-15 else 0.0
    return {
        "source": source_name,
        "half_life_days": t_half,
        "day_difference": days,
        "decay_factor_manual": manual,
        "decay_factor_tps": tps,
        "percent_deviation": pct,
    }


def apparent_activity_at_qa(
    activity_mci_calib: float,
    calib_dt: str,
    qa_dt: str,
    source_name: str = "Ir-192",
) -> dict:
    days = days_between(calib_dt, qa_dt)
    if days is None:
        raise ValueError("Could not parse dates")
    t_half = half_life_for_source(source_name)
    df = decay_factor(days, t_half)
    return {
        "source": source_name,
        "half_life_days": t_half,
        "day_difference": days,
        "decay_factor": df,
        "activity_mci": float(activity_mci_calib) * df,
    }


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
    sk = float(activity_mci_at_qa) * float(air_kerma_rate_const)
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


def multi_source_treatment_time(
    activity_mci_at_qa: float,
    air_kerma_rate_const: float = DEFAULT_AIR_KERMA_RATE_CONST,
    dose_rate_constant: float = DEFAULT_DOSE_RATE_CONSTANT,
    distances_mm: Sequence[float] = (14.14, 10.0, 14.14),
    g_values: Sequence[float] = (1.002284, 1.0, 1.002284),
    G_values: Sequence[float] = (0.500151045615776, 1.0, 0.500151045615776),
    F_values: Sequence[float] = (0.9613, 1.0, 0.960914),
    prescription_cgy: float = 1000.0,
    tps_time_s: Optional[float] = None,
) -> dict:
    sk = float(activity_mci_at_qa) * float(air_kerma_rate_const)
    contribs, total = [], 0.0
    for r_mm, g, G, F in zip(distances_mm, g_values, G_values, F_values):
        dr = sk * float(dose_rate_constant) * float(g) * float(G) * float(F)
        contribs.append({"distance_mm": float(r_mm), "g_r": float(g), "G": float(G), "F": float(F), "dose_rate_cgy_per_h": dr})
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


def within_tolerance(value: float, limit: float) -> bool:
    return abs(float(value)) <= abs(float(limit))


def status_label(ok: bool) -> str:
    return "Satisfactory" if ok else "Not satisfactory"
