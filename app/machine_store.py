"""Machines + beams: Supabase is the only source of truth."""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple


def _creds() -> Tuple[str, str]:
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    ).strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    return url, key


def supabase_configured() -> bool:
    url, key = _creds()
    return bool(url and key)


def _rest_headers(key: str, prefer: str = "return=minimal") -> dict:
    h = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _rest_get(path: str) -> List[dict]:
    url, key = _creds()
    if not url or not key:
        print("machine_store REST GET: no credentials")
        return []
    endpoint = url + "/rest/v1/" + path
    try:
        import httpx
        r = httpx.get(endpoint, headers=_rest_headers(key, ""), timeout=25.0)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
        print("machine_store REST GET", path, r.status_code, r.text[:300])
    except Exception as e:
        print("machine_store REST GET:", e)
    try:
        from app.db import use_db, sb_select
        if use_db():
            table = path.split("?")[0]
            return sb_select(table) or []
    except Exception as e:
        print("machine_store sb_select:", e)
    return []


def _rest_upsert(table: str, row: dict) -> bool:
    url, key = _creds()
    if not url or not key:
        print("machine_store REST upsert: no credentials")
        return False
    endpoint = url + "/rest/v1/" + table + "?on_conflict=id"
    headers = _rest_headers(key, "resolution=merge-duplicates,return=minimal")
    try:
        import httpx
        r = httpx.post(endpoint, headers=headers, json=row, timeout=25.0)
        if r.status_code in (200, 201, 204):
            print("machine_store REST upsert OK:", table, row.get("id") or row.get("name"))
            return True
        # retry without on_conflict
        r2 = httpx.post(
            url + "/rest/v1/" + table,
            headers=_rest_headers(key, "resolution=merge-duplicates,return=minimal"),
            json=row,
            timeout=25.0,
        )
        if r2.status_code in (200, 201, 204):
            print("machine_store REST upsert2 OK:", table)
            return True
        # PATCH by id
        rid = row.get("id")
        if rid:
            r3 = httpx.patch(
                url + "/rest/v1/" + table + "?id=eq." + str(rid),
                headers=_rest_headers(key, "return=minimal"),
                json=row,
                timeout=25.0,
            )
            if r3.status_code in (200, 204):
                print("machine_store REST PATCH OK:", table, rid)
                return True
            print("machine_store REST fail", table, r.status_code, r.text[:200], r2.status_code, r3.status_code)
        else:
            print("machine_store REST fail", table, r.status_code, r.text[:300])
    except Exception as e:
        print("machine_store REST upsert:", e)
    try:
        from app.db import use_db, sb_upsert
        if use_db():
            sb_upsert(table, row)
            print("machine_store sb_upsert OK:", table)
            return True
    except Exception as e:
        print("machine_store sb_upsert:", e)
    return False


def _rest_delete(table: str, row_id: str) -> bool:
    url, key = _creds()
    if not url or not key:
        return False
    try:
        import httpx
        r = httpx.delete(
            url + "/rest/v1/" + table + "?id=eq." + str(row_id),
            headers=_rest_headers(key, ""),
            timeout=20.0,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print("machine_store REST delete:", e)
    try:
        from app.db import use_db, sb_delete
        if use_db():
            return bool(sb_delete(table, row_id))
    except Exception as e:
        print("machine_store sb_delete:", e)
    return False


def machine_to_row(m) -> dict:
    return {
        "id": str(m.id),
        "name": str(getattr(m, "name", "") or ""),
        "manufacturer": str(getattr(m, "manufacturer", "") or ""),
        "model": str(getattr(m, "model", "") or ""),
        "serial_number": str(getattr(m, "serial_number", "") or ""),
        "location": str(getattr(m, "location", "") or ""),
        "notes": str(getattr(m, "notes", "") or ""),
        "category": str(getattr(m, "category", "ct_linac") or "ct_linac"),
    }


def beam_to_row(b) -> dict:
    return {
        "id": str(b.id),
        "machine_id": str(getattr(b, "linac_id", "") or ""),
        "modality": str(getattr(b, "modality", "photon") or "photon"),
        "nominal_energy": str(getattr(b, "nominal_energy", "") or ""),
        "measurement_depth_cm": float(getattr(b, "measurement_depth_cm", 10) or 10),
        "pdd": float(getattr(b, "pdd", 1) or 1),
        "k_q": float(getattr(b, "k_Q", 1) or 1),
        "quality_index": getattr(b, "quality_index", None),
        "ssd_cm": float(getattr(b, "ssd_cm", 100) or 100),
        "field_size": str(getattr(b, "field_size", "10x10") or "10x10"),
        "nominal_output_cgy_mu": float(getattr(b, "nominal_output_cGy_MU", 1) or 1),
        "notes": str(getattr(b, "notes", "") or ""),
    }


def _row_to_linac(r: dict):
    from app.models import Linac
    kwargs = dict(
        id=str(r["id"]),
        name=str(r.get("name") or ""),
        manufacturer=str(r.get("manufacturer") or ""),
        model=str(r.get("model") or ""),
        serial_number=str(r.get("serial_number") or ""),
        location=str(r.get("location") or ""),
        notes=str(r.get("notes") or ""),
    )
    cat = str(r.get("category") or "ct_linac")
    try:
        return Linac(**kwargs, category=cat)
    except TypeError:
        m = Linac(**kwargs)
        if hasattr(m, "category"):
            m.category = cat
        return m


def _row_to_beam(r: dict):
    from app.models import Beam
    return Beam(
        id=str(r["id"]),
        linac_id=str(r.get("machine_id") or ""),
        modality=str(r.get("modality") or "photon"),
        nominal_energy=str(r.get("nominal_energy") or ""),
        measurement_depth_cm=float(r.get("measurement_depth_cm") or 10),
        pdd=float(r.get("pdd") or 1),
        k_Q=float(r.get("k_q") or r.get("k_Q") or 1),
        quality_index=r.get("quality_index"),
        ssd_cm=float(r.get("ssd_cm") or 100),
        field_size=str(r.get("field_size") or "10x10"),
        nominal_output_cGy_MU=float(r.get("nominal_output_cgy_mu") or r.get("nominal_output_cGy_MU") or 1),
        notes=str(r.get("notes") or ""),
    )


def fetch_machines_from_supabase() -> List[dict]:
    return _rest_get("machines?select=*&order=name")


def fetch_beams_from_supabase() -> List[dict]:
    return _rest_get("beams?select=*&order=nominal_energy")


def hydrate_machines() -> int:
    """Replace in-memory machines/beams entirely from Supabase."""
    from app.models import add_linac, add_beam, _LINACS, _BEAMS

    if not supabase_configured():
        print("hydrate_machines: Supabase not configured")
        return 0

    mrows = fetch_machines_from_supabase()
    brows = fetch_beams_from_supabase()

    _LINACS.clear()
    _BEAMS.clear()

    n = 0
    for r in mrows:
        try:
            add_linac(_row_to_linac(r))
            n += 1
        except Exception as e:
            print("hydrate machine skip:", e)
    for r in brows:
        try:
            add_beam(_row_to_beam(r))
        except Exception as e:
            print("hydrate beam skip:", e)

    print("hydrate_machines: %d machines, %d beams from Supabase" % (n, len(brows)))
    return n


def save_machine_db(m) -> bool:
    """Upsert machine to Supabase then refresh memory from DB."""
    if not supabase_configured():
        print("save_machine_db: Supabase not configured")
        return False
    row = machine_to_row(m)
    ok = _rest_upsert("machines", row)
    if ok:
        # Keep memory in sync for current request
        try:
            from app.models import add_linac
            add_linac(m)
        except Exception:
            pass
        # Prefer full reload so all workers converge on next page load
        try:
            hydrate_machines()
        except Exception:
            pass
    return ok


def delete_machine_db(mid: str) -> bool:
    if not supabase_configured():
        return False
    # delete beams first if no cascade
    try:
        brows = fetch_beams_from_supabase()
        for r in brows:
            if str(r.get("machine_id")) == str(mid):
                _rest_delete("beams", str(r["id"]))
    except Exception as e:
        print("delete beams for machine:", e)
    ok = _rest_delete("machines", str(mid))
    try:
        hydrate_machines()
    except Exception:
        pass
    return ok


def save_beam_db(b) -> bool:
    if not supabase_configured():
        return False
    row = beam_to_row(b)
    ok = _rest_upsert("beams", row)
    if ok:
        try:
            from app.models import add_beam
            add_beam(b)
        except Exception:
            pass
        try:
            hydrate_machines()
        except Exception:
            pass
    return ok


def delete_beam_db(bid: str) -> bool:
    if not supabase_configured():
        return False
    ok = _rest_delete("beams", str(bid))
    try:
        hydrate_machines()
    except Exception:
        pass
    return ok


def list_machines_supabase_only():
    """Return Linac objects loaded only from Supabase (no stale memory)."""
    hydrate_machines()
    from app.models import list_linacs
    return list_linacs()


def list_beams_supabase_only(linac_id: Optional[str] = None):
    hydrate_machines()
    from app.models import list_beams
    return list_beams(linac_id=linac_id)
