"""In-memory + JSON file store for Daily QA and Mechanical QA checklists."""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA = Path(__file__).resolve().parent / "data"
_DAILY_FILE = _DATA / "daily_qa_items.json"
_MECH_FILE = _DATA / "mechanical_qa_items.json"

# item types: yes_no | numerical
# numerical: nominal, tol_ok (% or absolute), tol_warn (% or absolute), unit, mode: percent|absolute

DEFAULT_DAILY: List[dict] = [
    {"id": "d1", "label": "Door interlock functional", "item_type": "yes_no", "order": 1},
    {"id": "d2", "label": "Audiovisual monitors working", "item_type": "yes_no", "order": 2},
    {"id": "d3", "label": "Radiation area monitors OK", "item_type": "yes_no", "order": 3},
    {"id": "d4", "label": "Output constancy (cGy/MU)", "item_type": "numerical",
     "nominal": 1.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "%", "mode": "percent", "order": 4},
    {"id": "d5", "label": "Laser alignment (mm)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 5},
    {"id": "d6", "label": "ODI accuracy (mm)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "mm", "mode": "absolute", "order": 6},
]

DEFAULT_MECH: List[dict] = [
    {"id": "m1", "label": "Gantry angle indicator (deg)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 1},
    {"id": "m2", "label": "Collimator angle indicator (deg)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 2},
    {"id": "m3", "label": "Couch position accuracy (mm)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 3},
    {"id": "m4", "label": "Jaw symmetry / position (mm)", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 4},
    {"id": "m5", "label": "Light / radiation field coincidence", "item_type": "yes_no", "order": 5},
    {"id": "m6", "label": "Safety interlocks verified", "item_type": "yes_no", "order": 6},
]


def _load(path: Path, defaults: List[dict]) -> List[dict]:
    _DATA.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _save(path, defaults)
        return [dict(x) for x in defaults]
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            return [dict(x) for x in defaults]
        return data
    except Exception:
        return [dict(x) for x in defaults]


def _save(path: Path, rows: List[dict]) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))


def load_daily_items() -> List[dict]:
    return sorted(_load(_DAILY_FILE, DEFAULT_DAILY), key=lambda x: x.get("order", 0))


def save_daily_items(rows: List[dict]) -> None:
    _save(_DAILY_FILE, rows)


def load_mech_items() -> List[dict]:
    return sorted(_load(_MECH_FILE, DEFAULT_MECH), key=lambda x: x.get("order", 0))


def save_mech_items(rows: List[dict]) -> None:
    _save(_MECH_FILE, rows)


def new_id(prefix: str = "q") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def evaluate_numerical(item: dict, value: float) -> str:
    """Return 'green' | 'yellow' | 'red' for a numerical reading."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "red"
    nominal = float(item.get("nominal") or 0)
    tol_ok = float(item.get("tol_ok") or 0)
    tol_warn = float(item.get("tol_warn") or tol_ok)
    mode = (item.get("mode") or "absolute").lower()
    if mode == "percent":
        if nominal == 0:
            diff = abs(val)
            # treat as absolute if nominal 0
            ok_lim, warn_lim = tol_ok, tol_warn
        else:
            diff = abs(val - nominal) / abs(nominal) * 100.0
            ok_lim, warn_lim = tol_ok, tol_warn
    else:
        diff = abs(val - nominal)
        ok_lim, warn_lim = tol_ok, tol_warn
    if diff <= ok_lim:
        return "green"
    if diff <= warn_lim:
        return "yellow"
    return "red"


def evaluate_yes_no(answer: str) -> str:
    a = (answer or "").strip().lower()
    if a in ("yes", "y", "true", "1", "pass", "ok"):
        return "green"
    if a in ("no", "n", "false", "0", "fail"):
        return "red"
    return "yellow"
