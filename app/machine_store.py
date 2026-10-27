"""Machines + beams: Supabase is the only source of truth (REST)."""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

_LAST_ERROR = ""


def last_error() -> str:
    return _LAST_ERROR or ""


def _set_err(msg: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = str(msg or "")
    print("machine_store:", _LAST_ERROR)


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


def _headers(key: str, prefer: str = "") -> dict:
    h = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _http_json(method: str, endpoint: str, key: str, body=None, prefer: str = ""):
    import urllib.request
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers=_headers(key, prefer),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw
    except Exception as e:
        # HTTPError has code + body
        code = getattr(e, "code", None)
        body_txt = ""
        try:
            body_txt = e.read().decode("utf-8", errors="replace")  # type: ignore
        except Exception:
            body_txt = str(e)
        return code or 0, body_txt


def _rest_get(path: str) -> List[dict]:
    url, key = _creds()
    if not url or not key:
        _set_err("missing SUPABASE_URL or SUPABASE_KEY")
        return []
    status, raw = _http_json("GET", url + "/rest/v1/" + path, key)
    if status == 200:
        try:
            data = json.loads(raw or "[]")
            return data if isinstance(data, list) else []
        except Exception as e:
            _set_err("GET parse: " + str(e))
            return []
    _set_err("GET %s → %s %s" % (path, status, (raw or "")[:300]))
    return []


def _rest_upsert(table: str, row: dict) -> bool:
    """Upsert by id. Retries without category if column missing."""
    url, key = _creds()
    if not url or not key:
        _set_err("missing SUPABASE_URL or SUPABASE_KEY")
        return False

    attempts = [row]
    if "category" in row:
        slim = dict(row)
        slim.pop("category", None)
        attempts.append(slim)

    for attempt in attempts:
        # 1) POST with on_conflict=id
        status, raw = _http_json(
            "POST",
            url + "/rest/v1/" + table + "?on_conflict=id",
            key,
            body=attempt,
            prefer="resolution=merge-duplicates,return=representation",
        )
        if status in (200, 201):
            _set_err("")
            print("machine_store upsert OK", table, attempt.get("id"), status)
            return True
        if status == 204:
            _set_err("")
            return True

        # 2) PATCH by id
        rid = attempt.get("id")
        if rid:
            status2, raw2 = _http_json(
                "PATCH",
                url + "/rest/v1/" + table + "?id=eq." + str(rid),
                key,
                body=attempt,
                prefer="return=representation",
            )
            if status2 in (200, 204):
                # 0 rows updated is still 200 with [] — treat as need insert
                if status2 == 200 and (raw2 or "").strip() in ("", "[]"):
                    status3, raw3 = _http_json(
                        "POST",
                        url + "/rest/v1/" + table,
                        key,
                        body=attempt,
                        prefer="return=representation",
                    )
                    if status3 in (200, 201):
                        _set_err("")
                        return True
                    _set_err("POST insert %s → %s %s" % (table, status3, (raw3 or "")[:250]))
                    continue
                _set_err("")
                return True
            _set_err(
                "upsert %s failed POST %s %s | PATCH %s %s"
                % (table, status, (raw or "")[:150], status2, (raw2 or "")[:150])
            )
        else:
            _set_err("upsert %s failed %s %s" % (table, status, (raw or "")[:250]))

        # If error is unknown column category, next attempt drops it
        if "category" in (raw or "").lower() or "category" in (raw2 if rid else "" or "").lower():
            continue

    # last resort supabase-py
    try:
        from app.db import use_db, sb_upsert
        if use_db():
            sb_upsert(table, row)
            _set_err("")
            return True
    except Exception as e:
        _set_err("sb_upsert: " + str(e))
    return False


def _rest_delete(table: str, row_id: str) -> bool:
    url, key = _creds()
    if not url or not key:
        return False
    status, raw = _http_json(
        "DELETE",
        url + "/rest/v1/" + table + "?id=eq." + str(row_id),
        key,
    )
    ok = status in (200, 204)
    if not ok:
        _set_err("delete %s %s → %s %s" % (table, row_id, status, (raw or "")[:200]))
    return ok


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
    from app.models import add_linac, add_beam, _LINACS, _BEAMS

    if not supabase_configured():
        _set_err("Supabase not configured")
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
    print("hydrate_machines: %d machines, %d beams" % (n, len(brows)))
    return n


def save_machine_db(m) -> bool:
    if not supabase_configured():
        _set_err("Supabase not configured")
        return False
    ok = _rest_upsert("machines", machine_to_row(m))
    if ok:
        try:
            from app.models import add_linac
            add_linac(m)
        except Exception:
            pass
        try:
            hydrate_machines()
        except Exception:
            pass
    return ok


def delete_machine_db(mid: str) -> bool:
    if not supabase_configured():
        return False
    try:
        for r in fetch_beams_from_supabase():
            if str(r.get("machine_id")) == str(mid):
                _rest_delete("beams", str(r["id"]))
    except Exception as e:
        print("delete beams:", e)
    ok = _rest_delete("machines", str(mid))
    try:
        hydrate_machines()
    except Exception:
        pass
    return ok


def save_beam_db(b) -> bool:
    if not supabase_configured():
        _set_err("Supabase not configured")
        return False
    ok = _rest_upsert("beams", beam_to_row(b))
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
    hydrate_machines()
    from app.models import list_linacs
    return list_linacs()


def list_beams_supabase_only(linac_id: Optional[str] = None):
    hydrate_machines()
    from app.models import list_beams
    return list_beams(linac_id=linac_id)


def status_dict() -> dict:
    url, key = _creds()
    rows = []
    err = ""
    if url and key:
        rows = fetch_machines_from_supabase()
        err = last_error()
    return {
        "supabase_url_set": bool(url),
        "supabase_key_set": bool(key),
        "machines_count": len(rows or []),
        "machine_names": [r.get("name") for r in (rows or [])][:30],
        "last_error": err,
    }
