"""Machine-specific Daily QA and Mechanical QA checklist store."""
from __future__ import annotations
import json
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

_CANDIDATES = [
    Path("/tmp/dosepro_qa"),
    Path(__file__).resolve().parent / "data",
]

# Default templates applied when a machine has no items yet
DEFAULT_DAILY_TEMPLATE: List[dict] = [
    {"id": "d1", "label": "Door interlock functional", "item_type": "yes_no", "order": 1},
    {"id": "d2", "label": "Audiovisual monitors working", "item_type": "yes_no", "order": 2},
    {"id": "d3", "label": "Radiation area monitors OK", "item_type": "yes_no", "order": 3},
    {"id": "d4", "label": "Output constancy", "item_type": "numerical",
     "nominal": 1.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "%", "mode": "percent", "order": 4},
    {"id": "d5", "label": "Laser alignment", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 5},
    {"id": "d6", "label": "ODI accuracy", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "mm", "mode": "absolute", "order": 6},
]

DEFAULT_MECH_TEMPLATE: List[dict] = [
    {"id": "m1", "label": "Gantry angle indicator", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 1},
    {"id": "m2", "label": "Collimator angle indicator", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 2},
    {"id": "m3", "label": "Couch position accuracy", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 3},
    {"id": "m4", "label": "Jaw symmetry / position", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 4},
    {"id": "m5", "label": "Light / radiation field coincidence", "item_type": "yes_no", "order": 5},
    {"id": "m6", "label": "Safety interlocks verified", "item_type": "yes_no", "order": 6},
]

# In-memory: { linac_id: [items] }
_daily: Dict[str, List[dict]] = {}
_mech: Dict[str, List[dict]] = {}
_dir: Optional[Path] = None
_loaded = False


def _data_dir() -> Optional[Path]:
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


def _load_all() -> None:
    global _loaded, _daily, _mech
    if _loaded:
        return
    d = _data_dir()
    for name, target in [("daily_qa_by_machine.json", "daily"), ("mechanical_qa_by_machine.json", "mech")]:
        data = {}
        if d:
            path = d / name
            if path.exists():
                try:
                    raw = json.loads(path.read_text())
                    if isinstance(raw, dict):
                        data = raw
                    elif isinstance(raw, list):
                        # migrate old flat list → assign to "_default"
                        data = {"_default": raw}
                except Exception as e:
                    print("qa_store load error:", e)
        if target == "daily":
            _daily = data
        else:
            _mech = data
    _loaded = True


def _save(kind: str) -> None:
    d = _data_dir()
    if not d:
        return
    name = "daily_qa_by_machine.json" if kind == "daily" else "mechanical_qa_by_machine.json"
    data = _daily if kind == "daily" else _mech
    try:
        (d / name).write_text(json.dumps(data, indent=2))
    except Exception as e:
        print("qa_store save error:", e)


def _fresh_defaults(kind: str, linac_id: str) -> List[dict]:
    src = DEFAULT_DAILY_TEMPLATE if kind == "daily" else DEFAULT_MECH_TEMPLATE
    rows = []
    for it in src:
        row = deepcopy(it)
        row["id"] = new_id("d" if kind == "daily" else "m")
        row["linac_id"] = linac_id
        rows.append(row)
    return rows


def load_items(kind: str, linac_id: str, seed_if_empty: bool = True) -> List[dict]:
    """Load checklist items for one machine. Seeds defaults on first use."""
    _load_all()
    store = _daily if kind == "daily" else _mech
    lid = str(linac_id or "").strip()
    if not lid:
        return []
    if lid not in store or not store[lid]:
        if seed_if_empty:
            store[lid] = _fresh_defaults(kind, lid)
            _save(kind)
        else:
            return []
    rows = store[lid]
    return sorted(rows, key=lambda x: x.get("order", 0))


def save_items(kind: str, linac_id: str, rows: List[dict]) -> None:
    _load_all()
    lid = str(linac_id or "").strip()
    if not lid:
        return
    store = _daily if kind == "daily" else _mech
    for r in rows:
        r["linac_id"] = lid
    store[lid] = list(rows)
    _save(kind)


def load_daily_items(linac_id: str, seed_if_empty: bool = True) -> List[dict]:
    return load_items("daily", linac_id, seed_if_empty=seed_if_empty)


def save_daily_items(linac_id: str, rows: List[dict]) -> None:
    save_items("daily", linac_id, rows)


def load_mech_items(linac_id: str, seed_if_empty: bool = True) -> List[dict]:
    return load_items("mech", linac_id, seed_if_empty=seed_if_empty)


def save_mech_items(linac_id: str, rows: List[dict]) -> None:
    save_items("mech", linac_id, rows)


def new_id(prefix: str = "q") -> str:
    return "%s%s" % (prefix, uuid.uuid4().hex[:8])


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
