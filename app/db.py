"""
Supabase client for DOSE pro.
If SUPABASE_URL + SUPABASE_KEY are set → persistent storage.
Otherwise → falls back to in-memory (dev mode).
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

_SUPABASE = None
_USE_DB = False


def _init():
    global _SUPABASE, _USE_DB
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()  # service_role preferred, or anon
    if not url or not key:
        _USE_DB = False
        _SUPABASE = None
        return
    try:
        from supabase import create_client
        _SUPABASE = create_client(url, key)
        _USE_DB = True
    except Exception as e:
        print(f"[DOSE pro] Supabase init failed: {e} — using in-memory store")
        _USE_DB = False
        _SUPABASE = None


def use_db() -> bool:
    if _SUPABASE is None and not _USE_DB:
        _init()
    return _USE_DB and _SUPABASE is not None


def client():
    if not use_db():
        return None
    return _SUPABASE


def sb_select(table: str, filters: Optional[Dict[str, Any]] = None,
              order: Optional[str] = None, desc: bool = False) -> List[dict]:
    sb = client()
    if not sb:
        return []
    q = sb.table(table).select("*")
    if filters:
        for k, v in filters.items():
            if v is None:
                q = q.is_(k, "null")
            else:
                q = q.eq(k, v)
    if order:
        q = q.order(order, desc=desc)
    res = q.execute()
    return res.data or []


def sb_get(table: str, id_value: str, id_col: str = "id") -> Optional[dict]:
    rows = sb_select(table, {id_col: id_value})
    return rows[0] if rows else None


def sb_upsert(table: str, row: dict) -> dict:
    sb = client()
    if not sb:
        raise RuntimeError("Supabase not configured")
    res = sb.table(table).upsert(row).execute()
    return (res.data or [row])[0]


def sb_insert(table: str, row: dict) -> dict:
    sb = client()
    if not sb:
        raise RuntimeError("Supabase not configured")
    res = sb.table(table).insert(row).execute()
    return (res.data or [row])[0]


def sb_update(table: str, id_value: str, patch: dict, id_col: str = "id") -> Optional[dict]:
    sb = client()
    if not sb:
        raise RuntimeError("Supabase not configured")
    res = sb.table(table).update(patch).eq(id_col, id_value).execute()
    data = res.data or []
    return data[0] if data else None


def sb_delete(table: str, id_value: str, id_col: str = "id") -> bool:
    sb = client()
    if not sb:
        raise RuntimeError("Supabase not configured")
    sb.table(table).delete().eq(id_col, id_value).execute()
    return True


def status() -> dict:
    return {
        "supabase_configured": bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")),
        "using_database": use_db(),
        "mode": "supabase" if use_db() else "in-memory",
    }
