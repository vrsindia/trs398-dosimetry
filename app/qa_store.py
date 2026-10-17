"""Daily QA and Mechanical QA checklist store (memory + optional JSON file)."""
from __future__ import annotations
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import List

# Prefer writable locations (Render ephemeral disk)
_CANDIDATES = [
    Path("/tmp/dosepro_qa"),
    Path(__file__).resolve().parent / "data",
]

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

_mem_daily: List[dict] = deepcopy(DEFAULT_DAILY)
_mem_mech: List[dict] = deepcopy(DEFAULT_MECH)
_dir: Path | None = None
_loaded = False


def _data_dir() -> Path | None:
    global _dir
    if _dir is not None:
        return _dir
    for p in _CANDIDATES:
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / ".write_test"
            test.write_text("ok")
            test.unlink()
            _dir = p
            return _dir
        except Exception:
            continue
    _dir = None
    return None


def _load_file(name: str, defaults: List[dict]) -> List[dict]:
    d = _data_dir()
    if not d:
        return deepcopy(defaults)
    path = d / name
    if not path.exists():
        try:
            path.write_text(json.dumps(defaults, indent=2))
        except Exception:
            pass
        return deepcopy(defaults)
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return deepcopy(defaults)


def _save_file(name: str, rows: List[dict]) -> None:
    d = _data_dir()
    if not d:
        return
    try:
        (d / name).write_text(json.dumps(rows, indent=2))
    except Exception as e:
        print("qa_store save failed:", e)


def _ensure_loaded() -> None:
    global _loaded, _mem_daily, _mem_mech
    if _loaded:
        return
    _mem_daily = _load_file("daily_qa_items.json", DEFAULT_DAILY)
    _mem_mech = _load_file("mechanical_qa_items.json", DEFAULT_MECH)
    _loaded = True


def load_daily_items() -> List[dict]:
    _ensure_loaded()
    return sorted(_mem_daily, key=lambda x: x.get("order", 0))


def save_daily_items(rows: List[dict]) -> None:
    global _mem_daily
    _mem_daily = list(rows)
    _save_file("daily_qa_items.json", _mem_daily)


def load_mech_items() -> List[dict]:
    _ensure_loaded()
    return sorted(_mem_mech, key=lambda x: x.get("order", 0))


def save_mech_items(rows: List[dict]) -> None:
    global _mem_mech
    _mem_mech = list(rows)
    _save_file("mechanical_qa_items.json", _mem_mech)


def new_id(prefix: str = "q") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def evaluate_numerical(item: dict, value: float) -> str:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "red"
    nominal = float(item.get("nominal") or 0)
    tol_ok = float(item.get("tol_ok") or 0)
    tol_warn = float(item.get("tol_warn") or tol_ok)
    mode = (item.get("mode") or "absolute").lower()
    if mode == "percent" and nominal != 0:
        diff = abs(val - nominal) / abs(nominal) * 100.0
    else:
        diff = abs(val - nominal)
    if diff <= tol_ok:
        return "green"
    if diff <= tol_warn:
        return "yellow"
    return "red"


def evaluate_yes_no(answer: str) -> str:
    a = (answer or "").strip().lower()
    if a in ("yes", "y", "true", "1", "pass", "ok"):
        return "green"
    if a in ("no", "n", "false", "0", "fail"):
        return "red"
    return "yellow"
