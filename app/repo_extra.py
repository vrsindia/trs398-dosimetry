"""Supabase persistence for tolerances and app users."""
from __future__ import annotations
from typing import List, Optional

from app.db import use_db, sb_select, sb_get, sb_upsert, sb_delete
from app.models import (
    ToleranceTable,
    add_tolerance as mem_add_tol,
    get_tolerance as mem_get_tol,
    list_tolerances as mem_list_tol,
    delete_tolerance as mem_del_tol,
)


def list_tolerances(linac_id: Optional[str] = None) -> List[ToleranceTable]:
    if not use_db():
        return mem_list_tol()
    filters = {"linac_id": linac_id} if linac_id else None
    rows = sb_select("tolerances", filters, order="name")
    out = []
    for r in rows:
        out.append(ToleranceTable(
            id=r["id"],
            name=r.get("name") or "",
            linac_id=r.get("linac_id"),
            modality=r.get("modality") or "photon",
            energy=r.get("energy"),
            parameter=r.get("parameter") or "output",
            tolerance_percent=float(r.get("tolerance_percent") or 2),
            action_level_percent=r.get("action_level_percent"),
            baseline_value=r.get("baseline_value"),
            notes=r.get("notes") or "",
        ))
    return out


def get_tolerance(tid: str) -> Optional[ToleranceTable]:
    if not use_db():
        return mem_get_tol(tid)
    r = sb_get("tolerances", tid)
    if not r:
        return None
    return ToleranceTable(
        id=r["id"], name=r.get("name") or "",
        linac_id=r.get("linac_id"), modality=r.get("modality") or "photon",
        energy=r.get("energy"), parameter=r.get("parameter") or "output",
        tolerance_percent=float(r.get("tolerance_percent") or 2),
        action_level_percent=r.get("action_level_percent"),
        baseline_value=r.get("baseline_value"), notes=r.get("notes") or "",
    )


def save_tolerance(t: ToleranceTable) -> ToleranceTable:
    if not use_db():
        mem_add_tol(t)
        return t
    sb_upsert("tolerances", {
        "id": t.id, "name": t.name, "linac_id": t.linac_id,
        "modality": t.modality, "energy": t.energy,
        "parameter": t.parameter,
        "tolerance_percent": t.tolerance_percent,
        "action_level_percent": t.action_level_percent,
        "baseline_value": t.baseline_value, "notes": t.notes,
    })
    return t


def delete_tolerance(tid: str) -> bool:
    if not use_db():
        return mem_del_tol(tid)
    return sb_delete("tolerances", tid)


def save_user_row(user) -> None:
    from app.user_store import persist_user
    persist_user(user)


def load_users_from_db():
    from app.user_store import load_all_user_rows
    return load_all_user_rows()


def delete_user_row(user_id: str) -> bool:
    from app.user_store import remove_user
    remove_user(user_id)
    return True
