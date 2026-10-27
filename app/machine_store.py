"""Load/save machines + beams to Supabase (machines / beams tables)."""
from __future__ import annotations

from typing import List, Optional


def _use_db() -> bool:
    try:
        from app.db import use_db
        return bool(use_db())
    except Exception:
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


def save_machine_db(m) -> bool:
    """Upsert machine to Supabase + memory."""
    from app.models import add_linac
    add_linac(m)
    if not _use_db():
        print("save_machine_db: no DB — memory only")
        return False
    row = machine_to_row(m)
    try:
        from app.db import sb_upsert
        sb_upsert("machines", row)
        print("save_machine_db OK:", row["name"])
        return True
    except Exception as e:
        print("save_machine_db sb_upsert:", e)
    # REST fallback
    try:
        import os, json, urllib.request
        url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not url or not key:
            return False
        req = urllib.request.Request(
            url + "/rest/v1/machines?on_conflict=id",
            data=json.dumps(row).encode("utf-8"),
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            print("save_machine_db REST OK:", row["name"], resp.status)
            return True
    except Exception as e:
        print("save_machine_db REST:", e)
        return False


def delete_machine_db(mid: str) -> bool:
    from app.models import delete_linac
    delete_linac(mid)
    if not _use_db():
        return True
    try:
        from app.db import sb_delete
        return bool(sb_delete("machines", mid))
    except Exception as e:
        print("delete_machine_db:", e)
        return False


def save_beam_db(b) -> bool:
    from app.models import add_beam
    add_beam(b)
    if not _use_db():
        return False
    row = beam_to_row(b)
    try:
        from app.db import sb_upsert
        sb_upsert("beams", row)
        print("save_beam_db OK:", row["nominal_energy"])
        return True
    except Exception as e:
        print("save_beam_db:", e)
        return False


def delete_beam_db(bid: str) -> bool:
    from app.models import delete_beam
    delete_beam(bid)
    if not _use_db():
        return True
    try:
        from app.db import sb_delete
        return bool(sb_delete("beams", bid))
    except Exception as e:
        print("delete_beam_db:", e)
        return False


def hydrate_machines() -> int:
    """Pull machines + beams from Supabase into in-memory models."""
    from app.models import Linac, Beam, add_linac, add_beam, _LINACS, _BEAMS

    if not _use_db():
        print("hydrate_machines: no DB")
        return len(_LINACS)

    try:
        from app.db import sb_select
        mrows = sb_select("machines", order="name") or []
        brows = sb_select("beams", order="nominal_energy") or []
    except Exception as e:
        print("hydrate_machines select:", e)
        return len(_LINACS)

    # Rebuild memory from DB (authoritative)
    _LINACS.clear()
    _BEAMS.clear()
    n = 0
    for r in mrows:
        try:
            m = Linac(
                id=str(r["id"]),
                name=str(r.get("name") or ""),
                manufacturer=str(r.get("manufacturer") or ""),
                model=str(r.get("model") or ""),
                serial_number=str(r.get("serial_number") or ""),
                location=str(r.get("location") or ""),
                notes=str(r.get("notes") or ""),
                category=str(r.get("category") or "ct_linac"),
            )
            add_linac(m)
            n += 1
        except TypeError:
            try:
                m = Linac(
                    id=str(r["id"]),
                    name=str(r.get("name") or ""),
                    manufacturer=str(r.get("manufacturer") or ""),
                    model=str(r.get("model") or ""),
                    serial_number=str(r.get("serial_number") or ""),
                    location=str(r.get("location") or ""),
                    notes=str(r.get("notes") or ""),
                )
                if hasattr(m, "category"):
                    m.category = str(r.get("category") or "ct_linac")
                add_linac(m)
                n += 1
            except Exception as e:
                print("hydrate machine skip:", e)
        except Exception as e:
            print("hydrate machine skip:", e)

    for r in brows:
        try:
            b = Beam(
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
            add_beam(b)
        except Exception as e:
            print("hydrate beam skip:", e)

    print("hydrate_machines: %d machines, %d beams" % (n, len(brows)))
    return n
