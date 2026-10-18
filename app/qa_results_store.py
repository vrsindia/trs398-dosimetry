"""Persist Daily QA and Mechanical QA evaluation sessions (Supabase + local)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

TABLE = "qa_results"

_CANDIDATES = [
    Path("/tmp/dosepro_qa"),
    Path(__file__).resolve().parent / "data",
]

_mem: List[dict] = []
_loaded = False
_dir = None


def _new_id():
    return "qa" + uuid.uuid4().hex[:12]


def _data_dir():
    global _dir
    if _dir is not None:
        return _dir
    for p in _CANDIDATES:
        try:
            p.mkdir(parents=True, exist_ok=True)
            t = p / ".w"
            t.write_text("ok")
            t.unlink()
            _dir = p
            return _dir
        except Exception:
            continue
    return None


def _load_local():
    global _loaded, _mem
    if _loaded:
        return
    d = _data_dir()
    if d:
        path = d / "qa_results.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, list):
                    _mem = data
            except Exception as e:
                print("qa_results load:", e)
    _loaded = True


def _save_local():
    d = _data_dir()
    if not d:
        return
    try:
        (d / "qa_results.json").write_text(json.dumps(_mem, indent=2, default=str))
    except Exception as e:
        print("qa_results save:", e)


def save_qa_result(
    kind: str,
    linac_id: str,
    linac_name: str,
    overall: str,
    results: List[dict],
    performed_by: str,
    notes: str = "",
    performed_at: Optional[str] = None,
) -> dict:
    """Save one evaluation session. kind = daily | mechanical."""
    _load_local()
    row = {
        "id": _new_id(),
        "kind": kind,
        "linac_id": str(linac_id or ""),
        "linac_name": linac_name or str(linac_id or ""),
        "performed_at": performed_at or datetime.utcnow().isoformat() + "Z",
        "performed_by": performed_by or "",
        "overall": overall or "",
        "results": results or [],
        "notes": notes or "",
    }
    # Supabase first
    try:
        from app.db import use_db, sb_insert
        if use_db():
            payload = dict(row)
            # store results as json-serializable
            payload["results"] = results
            sb_insert(TABLE, payload)
    except Exception as e:
        print("qa_results supabase insert:", e)

    _mem.insert(0, row)
    _save_local()
    return row


def list_qa_results(
    kind: Optional[str] = None,
    linac_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[dict]:
    """List sessions newest first. Dates as YYYY-MM-DD inclusive."""
    rows: List[dict] = []
    try:
        from app.db import use_db, sb_select
        if use_db():
            filters = {}
            if kind:
                filters["kind"] = kind
            if linac_id:
                filters["linac_id"] = linac_id
            rows = sb_select(TABLE, filters or None, order="performed_at", desc=True) or []
    except Exception as e:
        print("qa_results supabase list:", e)
        rows = []

    if not rows:
        _load_local()
        rows = list(_mem)

    out = []
    for r in rows:
        if kind and r.get("kind") != kind:
            continue
        if linac_id and str(r.get("linac_id") or "") != str(linac_id):
            continue
        pa = (r.get("performed_at") or "")[:10]
        if date_from and pa and pa < date_from:
            continue
        if date_to and pa and pa > date_to:
            continue
        # normalize results field
        res = r.get("results")
        if isinstance(res, str):
            try:
                r = dict(r)
                r["results"] = json.loads(res)
            except Exception:
                pass
        out.append(r)

    out.sort(key=lambda x: x.get("performed_at") or "", reverse=True)
    return out


def get_qa_result(rid: str) -> Optional[dict]:
    try:
        from app.db import use_db, sb_get
        if use_db():
            row = sb_get(TABLE, rid)
            if row:
                res = row.get("results")
                if isinstance(res, str):
                    try:
                        row["results"] = json.loads(res)
                    except Exception:
                        pass
                return row
    except Exception as e:
        print("qa_results get:", e)
    _load_local()
    for r in _mem:
        if r.get("id") == rid:
            return r
    return None


def delete_qa_result(rid: str) -> bool:
    try:
        from app.db import use_db, sb_delete
        if use_db():
            sb_delete(TABLE, rid)
    except Exception as e:
        print("qa_results delete sb:", e)
    _load_local()
    global _mem
    before = len(_mem)
    _mem = [r for r in _mem if r.get("id") != rid]
    _save_local()
    return len(_mem) < before


def week_bounds(any_day: str):
    """Return (monday, sunday) YYYY-MM-DD for the week containing any_day."""
    d = datetime.strptime(any_day[:10], "%Y-%m-%d")
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")
