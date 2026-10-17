"""
Extra utility calculators:
- Equivalent square field
- MU (photon / electron) simple estimates
- Units converter
- Isotope half-lives
- OAR constraints library (conventional + 1/2/3/5 fraction)
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import math

ISOTOPES: Dict[str, dict] = {
    "Ir-192": {"half_life_days": 73.83, "unit": "days", "use": "HDR brachytherapy"},
    "Co-60": {"half_life_days": 1925.2, "unit": "days", "use": "Teletherapy / HDR"},
    "Cs-137": {"half_life_days": 11019.0, "unit": "days", "use": "LDR / calibration"},
    "I-125": {"half_life_days": 59.4, "unit": "days", "use": "LDR seeds"},
    "Pd-103": {"half_life_days": 16.99, "unit": "days", "use": "LDR seeds"},
    "Au-198": {"half_life_days": 2.70, "unit": "days", "use": "LDR seeds"},
    "Ra-226": {"half_life_days": 584400.0, "unit": "days", "use": "Historical"},
    "Sr-90": {"half_life_days": 10512.0, "unit": "days", "use": "Ophthalmic / beta"},
    "Y-90": {"half_life_days": 2.67, "unit": "days", "use": "Radioembolisation"},
    "I-131": {"half_life_days": 8.02, "unit": "days", "use": "Thyroid"},
    "Tc-99m": {"half_life_days": 0.2504, "unit": "days", "use": "Diagnostic"},
    "F-18": {"half_life_days": 0.076, "unit": "days", "use": "PET"},
}


def decay_activity(a0: float, half_life_days: float, elapsed_days: float) -> dict:
    if half_life_days <= 0:
        raise ValueError("Half-life must be positive.")
    factor = math.exp(-math.log(2) * elapsed_days / half_life_days)
    return {
        "a0": a0,
        "half_life_days": half_life_days,
        "elapsed_days": elapsed_days,
        "activity": a0 * factor,
        "decay_factor": factor,
    }


def equivalent_square(length: float, width: float) -> dict:
    L, W = float(length), float(width)
    if L <= 0 or W <= 0:
        raise ValueError("Length and width must be positive.")
    eq = 2.0 * L * W / (L + W)
    return {"length": L, "width": W, "eq_square": eq, "area": L * W, "perimeter": 2 * (L + W)}


def equivalent_square_circular(diameter: float) -> dict:
    d = float(diameter)
    if d <= 0:
        raise ValueError("Diameter must be positive.")
    eq = d * math.sqrt(math.pi / 4.0)
    return {"diameter": d, "eq_square": eq, "area": math.pi * (d / 2) ** 2}


def mu_photon_ssd(
    dose_cgy: float, output_cgy_mu: float, sc: float = 1.0, sp: float = 1.0,
    tmr_or_pdd: float = 1.0, sad_factor: float = 1.0, wedge: float = 1.0,
    tray: float = 1.0, other: float = 1.0,
) -> dict:
    dose = float(dose_cgy)
    out = float(output_cgy_mu)
    product = out * sc * sp * tmr_or_pdd * sad_factor * wedge * tray * other
    if product <= 0:
        raise ValueError("Product of factors must be positive.")
    return {
        "modality": "photon_ssd", "dose_cgy": dose, "output_cgy_mu": out,
        "sc": sc, "sp": sp, "tmr_or_pdd": tmr_or_pdd, "sad_factor": sad_factor,
        "wedge": wedge, "tray": tray, "other": other, "mu": dose / product,
    }


def mu_photon_sad(
    dose_cgy: float, output_cgy_mu: float, sc: float = 1.0, sp: float = 1.0,
    tmr: float = 1.0, inv_square: float = 1.0, wedge: float = 1.0,
    tray: float = 1.0, other: float = 1.0,
) -> dict:
    product = output_cgy_mu * sc * sp * tmr * inv_square * wedge * tray * other
    if product <= 0:
        raise ValueError("Product of factors must be positive.")
    return {
        "modality": "photon_sad", "dose_cgy": dose_cgy, "output_cgy_mu": output_cgy_mu,
        "sc": sc, "sp": sp, "tmr": tmr, "inv_square": inv_square,
        "wedge": wedge, "tray": tray, "other": other, "mu": dose_cgy / product,
    }


def mu_electron(
    dose_cgy: float, output_cgy_mu: float, applicator_factor: float = 1.0,
    cutout_factor: float = 1.0, ssdf: float = 1.0, other: float = 1.0,
) -> dict:
    product = output_cgy_mu * applicator_factor * cutout_factor * ssdf * other
    if product <= 0:
        raise ValueError("Product of factors must be positive.")
    return {
        "modality": "electron", "dose_cgy": dose_cgy, "output_cgy_mu": output_cgy_mu,
        "applicator_factor": applicator_factor, "cutout_factor": cutout_factor,
        "ssdf": ssdf, "other": other, "mu": dose_cgy / product,
    }


_DOSE = {"Gy": 1.0, "cGy": 0.01, "mGy": 0.001, "rad": 0.01}
_ACTIVITY = {"Bq": 1.0, "kBq": 1e3, "MBq": 1e6, "GBq": 1e9, "Ci": 3.7e10, "mCi": 3.7e7, "uCi": 3.7e4}
_LENGTH = {"cm": 1.0, "mm": 0.1, "m": 100.0, "in": 2.54}
_TIME = {"days": 1.0, "hours": 1.0 / 24.0, "min": 1.0 / 1440.0, "years": 365.25}


def convert_units(value: float, from_unit: str, to_unit: str, category: str) -> dict:
    tables = {"dose": _DOSE, "activity": _ACTIVITY, "length": _LENGTH, "time": _TIME}
    cat = category.lower().strip()
    if cat not in tables:
        raise ValueError(f"Unknown category: {category}")
    table = tables[cat]
    lookup = {k.lower(): k for k in table}
    fu, tu = from_unit.strip(), to_unit.strip()
    if fu.lower() not in lookup or tu.lower() not in lookup:
        raise ValueError(f"Unsupported unit for {category}: {from_unit} → {to_unit}")
    fu, tu = lookup[fu.lower()], lookup[tu.lower()]
    base = float(value) * table[fu]
    result = base / table[tu]
    return {"value": float(value), "from_unit": fu, "to_unit": tu, "category": cat, "result": result}


UNIT_OPTIONS = {
    "dose": list(_DOSE.keys()),
    "activity": list(_ACTIVITY.keys()),
    "length": list(_LENGTH.keys()),
    "time": list(_TIME.keys()),
}

_DATA = Path(__file__).resolve().parent.parent / "data"
_CONSTRAINTS_FILE = _DATA / "nt_constraints.json"

# Fractionation scheme keys used in the OAR library
FX_SCHEMES = (
    ("conventional_gy", "Conventional"),
    ("fx1_gy", "1 fraction"),
    ("fx2_gy", "2 fractions"),
    ("fx3_gy", "3 fractions"),
    ("fx5_gy", "5 fractions"),
)


def _normalize_row(c: dict) -> dict:
    """Migrate old {eqd2_gy} rows and ensure all fx keys exist."""
    out = {
        "organ": c.get("organ") or "",
        "endpoint": c.get("endpoint") or "",
        "metric": c.get("metric") or "Dmax",
        "conventional_gy": c.get("conventional_gy"),
        "fx1_gy": c.get("fx1_gy"),
        "fx2_gy": c.get("fx2_gy"),
        "fx3_gy": c.get("fx3_gy"),
        "fx5_gy": c.get("fx5_gy"),
        "notes": c.get("notes") or "",
    }
    # Legacy single EQD2 field → conventional
    if out["conventional_gy"] is None and c.get("eqd2_gy") is not None:
        try:
            out["conventional_gy"] = float(c["eqd2_gy"])
        except (TypeError, ValueError):
            pass
    return out


def load_constraints() -> List[dict]:
    _DATA.mkdir(parents=True, exist_ok=True)
    if not _CONSTRAINTS_FILE.exists():
        # Seed from packaged defaults if present; else empty
        try:
            raw = _CONSTRAINTS_FILE.read_text() if _CONSTRAINTS_FILE.exists() else ""
        except Exception:
            raw = ""
        if not raw:
            return []
    try:
        data = json.loads(_CONSTRAINTS_FILE.read_text())
        return [_normalize_row(c) for c in data]
    except Exception:
        return []


def save_constraints(rows: List[dict]) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    cleaned = [_normalize_row(c) for c in rows]
    _CONSTRAINTS_FILE.write_text(json.dumps(cleaned, indent=2))


def _opt_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def constraint_from_form(
    organ: str,
    endpoint: str = "",
    metric: str = "Dmax",
    conventional_gy=None,
    fx1_gy=None,
    fx2_gy=None,
    fx3_gy=None,
    fx5_gy=None,
    notes: str = "",
) -> dict:
    return _normalize_row({
        "organ": organ,
        "endpoint": endpoint,
        "metric": metric,
        "conventional_gy": _opt_float(conventional_gy),
        "fx1_gy": _opt_float(fx1_gy),
        "fx2_gy": _opt_float(fx2_gy),
        "fx3_gy": _opt_float(fx3_gy),
        "fx5_gy": _opt_float(fx5_gy),
        "notes": notes,
    })
