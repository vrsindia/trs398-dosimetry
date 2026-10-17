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

DEFAULT_DAILY_TEMPLATE: List[dict] = [
    {"label": "Door interlock functional", "item_type": "yes_no", "order": 1},
    {"label": "Audiovisual monitors working", "item_type": "yes_no", "order": 2},
    {"label": "Radiation area monitors OK", "item_type": "yes_no", "order": 3},
    {"label": "Output constancy", "item_type": "numerical",
     "nominal": 1.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "%", "mode": "percent", "order": 4},
    {"label": "Laser alignment", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 5},
    {"label": "ODI accuracy", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 2.0, "tol_warn": 3.0, "unit": "mm", "mode": "absolute", "order": 6},
]

DEFAULT_MECH_TEMPLATE: List[dict] = [
    {"label": "Gantry angle indicator", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 1},
    {"label": "Collimator angle indicator", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 0.5, "tol_warn": 1.0, "unit": "deg", "mode": "absolute", "order": 2},
    {"label": "Couch position accuracy", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 3},
    {"label": "Jaw symmetry / position", "item_type": "numerical",
     "nominal": 0.0, "tol_ok": 1.0, "tol_warn": 2.0, "unit": "mm", "mode": "absolute", "order": 4},
    {"label": "Light / radiation field coincidence", "item_type": "yes_no", "order": 5},
    {"label": "Safety interlocks verified", "item_type": "yes_no", "order": 6},
]

_daily: Dict[str, List[dict]] = {}
_mech: Dict[str, List[dict]] = {}
_dir = None  # type: Optional[Path]
_loaded = False


def new_id(prefix="q"):
    return "%s%s" % (prefix, uuid.uuid4().hex[:8])


def _data_dir():
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


def _load_all():
    global _loaded, _daily, _mech
    if _loaded:
        return
    d = _data_dir()
    for name, target in [("daily_qa_by_machine.json", "daily"),
                         ("mechanical_qa_by_machine.json", "mech")]:
        data = {}
        if d:
            path = d / name
            if path.exists():
                try:
                    raw = json.loads(path.read_text())
                    if isinstance(raw, dict):
                        data = {str(k): list(v) for k, v in raw.items() if isinstance(v, list)}
                    elif isinstance(raw, list):
                        data = {"_default": raw}
                except Exception as e:
                    print("qa_store load error:", e)
        if target == "daily":
            _daily = data
        else:
            _mech = data
    _loaded = True


def _save(kind):
    d = _data_dir()
    if not d:
        return
    name = "daily_qa_by_machine.json" if kind == "daily" else "mechanical_qa_by_machine.json"
    data = _daily if kind == "daily" else _mech
    try:
        (d / name).write_text(json.dumps(data, indent=2))
    except Exception as e:
        print("qa_store save error:", e)


def _fresh_defaults(kind, linac_id):
    src = DEFAULT_DAILY_TEMPLATE if kind == "daily" else DEFAULT_MECH_TEMPLATE
    prefix = "d" if kind == "daily" else "m"
    rows = []
    for it in src:
        row = deepcopy(it)
        row["id"] = new_id(prefix)
        row["linac_id"] = str(linac_id)
        rows.append(row)
    return rows


def load_items(kind, linac_id, seed_if_empty=True):
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
    return sorted(list(store[lid]), key=lambda x: int(x.get("order") or 0))


def save_items(kind, linac_id, rows):
    _load_all()
    lid = str(linac_id or "").strip()
    if not lid:
        return
    store = _daily if kind == "daily" else _mech
    cleaned = []
    for r in rows:
        rr = dict(r)
        rr["linac_id"] = lid
        if not rr.get("id"):
            rr["id"] = new_id("d" if kind == "daily" else "m")
        cleaned.append(rr)
    store[lid] = cleaned
    _save(kind)


def load_daily_items(linac_id, seed_if_empty=True):
    return load_items("daily", linac_id, seed_if_empty=seed_if_empty)


def save_daily_items(linac_id, rows):
    save_items("daily", linac_id, rows)


def load_mech_items(linac_id, seed_if_empty=True):
    return load_items("mech", linac_id, seed_if_empty=seed_if_empty)


def save_mech_items(linac_id, rows):
    save_items("mech", linac_id, rows)


def evaluate_numerical(item, value):
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "red"
    try:
        nominal = float(item.get("nominal") or 0)
        tol_ok = float(item.get("tol_ok") or 0)
        tol_warn = float(item.get("tol_warn") or tol_ok)
    except (TypeError, ValueError):
        return "red"
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


def evaluate_yes_no(answer):
    a = (answer or "").strip().lower()
    if a in ("yes", "y", "true", "1", "pass", "ok"):
        return "green"
    if a in ("no", "n", "false", "0", "fail"):
        return "red"
    return "yellow"
