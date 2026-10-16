"""
Radioactive source activity decay calculator.
A(t) = A0 * exp(-λ t),  λ = ln(2) / T½
Supports Bq and Ci (1 Ci = 3.7e10 Bq).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date
from math import log, exp
from typing import Dict, Optional, Tuple

LN2 = log(2.0)
BQ_PER_CI = 3.7e10

# Half-lives in days (clinical reference values)
HALF_LIVES_DAYS: Dict[str, float] = {
    "Co-60": 5.2714 * 365.25,
    "Ir-192": 73.83,
    "Ra-226": 1600.0 * 365.25,
    "I-125": 59.49,
    "I-131": 8.0233,
    "Ru-106": 371.8,
    "Cs-137": 30.08 * 365.25,
    "Au-198": 2.6947,
    "Pd-103": 16.991,
    "Sr-90": 28.79 * 365.25,
    "Y-90": 64.1 / 24.0,
    "F-18": 109.77 / (60.0 * 24.0),
    "Tc-99m": 6.007 / 24.0,
    "Am-241": 432.6 * 365.25,
    "Cf-252": 2.645 * 365.25,
    "P-32": 14.268,
    "Sm-153": 46.284 / 24.0,
    "Lu-177": 6.647,
    "Ra-223": 11.43,
    "Ac-225": 9.92,
}

# Alias common misspellings / alternate names
ALIASES = {
    "I-121": "I-125",  # likely meant I-125
    "I121": "I-125",
    "I125": "I-125",
    "Co60": "Co-60",
    "Ir192": "Ir-192",
    "Ra226": "Ra-226",
    "Ru106": "Ru-106",
    "Cs137": "Cs-137",
}


def list_sources() -> list:
    return sorted(HALF_LIVES_DAYS.keys())


def resolve_source(name: str) -> str:
    name = (name or "").strip()
    if name in HALF_LIVES_DAYS:
        return name
    if name in ALIASES:
        return ALIASES[name]
    # case-insensitive
    for k in HALF_LIVES_DAYS:
        if k.lower() == name.lower():
            return k
    raise ValueError(f"Unknown source: {name}")


def to_bq(activity: float, unit: str) -> float:
    u = unit.lower().strip()
    if u == "bq":
        return activity
    if u == "ci":
        return activity * BQ_PER_CI
    if u == "mci":
        return activity * 1e-3 * BQ_PER_CI
    if u == "uci":
        return activity * 1e-6 * BQ_PER_CI
    if u == "mbq":
        return activity * 1e6
    if u == "gbq":
        return activity * 1e9
    raise ValueError(f"Unknown unit: {unit}")


def from_bq(activity_bq: float, unit: str) -> float:
    u = unit.lower().strip()
    if u == "bq":
        return activity_bq
    if u == "ci":
        return activity_bq / BQ_PER_CI
    if u == "mci":
        return activity_bq / (1e-3 * BQ_PER_CI)
    if u == "uci":
        return activity_bq / (1e-6 * BQ_PER_CI)
    if u == "mbq":
        return activity_bq / 1e6
    if u == "gbq":
        return activity_bq / 1e9
    raise ValueError(f"Unknown unit: {unit}")


def parse_date(s: str) -> date:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {s} (use YYYY-MM-DD)")


@dataclass
class ActivityResult:
    source: str
    half_life_days: float
    reference_activity_bq: float
    current_activity_bq: float
    elapsed_days: float
    decay_factor: float
    unit_in: str
    unit_out: str
    reference_activity_display: float
    current_activity_display: float
    current_activity_ci: float
    current_activity_bq_out: float
    mode: str  # "days" | "dates"


def calculate_activity(
    source: str,
    reference_activity: float,
    unit: str = "Ci",
    *,
    days: Optional[float] = None,
    reference_date: Optional[str] = None,
    calculation_date: Optional[str] = None,
    output_unit: Optional[str] = None,
) -> ActivityResult:
    """
    Decay activity from a reference value.
    Provide either `days` OR both reference_date and calculation_date.
    """
    src = resolve_source(source)
    t_half = HALF_LIVES_DAYS[src]
    unit_in = unit
    unit_out = output_unit or unit

    a0_bq = to_bq(float(reference_activity), unit_in)

    if days is not None and days != "":
        elapsed = float(days)
        mode = "days"
    elif reference_date and calculation_date:
        d0 = parse_date(reference_date)
        d1 = parse_date(calculation_date)
        elapsed = (d1 - d0).days + (d1 - d0).seconds / 86400.0 if False else float((d1 - d0).days)
        # use fractional days from datetime if times present — dates only: whole days
        elapsed = float((d1 - d0).days)
        mode = "dates"
    else:
        raise ValueError("Provide either days, or both reference_date and calculation_date")

    lam = LN2 / t_half
    factor = exp(-lam * elapsed)
    a_bq = a0_bq * factor

    return ActivityResult(
        source=src,
        half_life_days=t_half,
        reference_activity_bq=a0_bq,
        current_activity_bq=a_bq,
        elapsed_days=elapsed,
        decay_factor=factor,
        unit_in=unit_in,
        unit_out=unit_out,
        reference_activity_display=float(reference_activity),
        current_activity_display=from_bq(a_bq, unit_out),
        current_activity_ci=from_bq(a_bq, "Ci"),
        current_activity_bq_out=a_bq,
        mode=mode,
    )
