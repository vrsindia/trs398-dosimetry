"""Persistent user store: Supabase REST (reliable) + JSON backup."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

_DATA_DIRS = [
    Path(__file__).resolve().parent / "data",
    Path("/tmp/dosepro"),
]
_JSON_NAME = "app_users.json"


def _json_path() -> Path:
    for d in _DATA_DIRS:
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / _JSON_NAME
            if not p.exists():
                p.write_text("[]", encoding="utf-8")
            return p
        except Exception:
            continue
    return Path("/tmp") / _JSON_NAME


def _user_to_dict(user) -> dict:
    perms = getattr(user, "permissions", set()) or set()
    if not isinstance(perms, (list, set, tuple)):
        perms = []
    return {
        "id": str(user.id),
        "username": str(user.username),
        "full_name": str(getattr(user, "full_name", "") or user.username),
        "role": str(getattr(user, "role", "observer") or "observer"),
        "password_hash": str(user.password_hash),
        "salt": str(user.salt),
        "active": bool(getattr(user, "active", True)),
        "permissions": sorted(list(perms)),
        "created_at": str(getattr(user, "created_at", "") or ""),
        "created_by": str(getattr(user, "created_by", "") or ""),
    }


def _supabase_creds():
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


def save_user_json(user) -> None:
    try:
        path = _json_path()
        rows: List[dict] = []
        if path.exists():
            try:
                rows = json.loads(path.read_text(encoding="utf-8") or "[]")
                if not isinstance(rows, list):
                    rows = []
            except Exception:
                rows = []
        row = _user_to_dict(user)
        found = False
        for i, r in enumerate(rows):
            if r.get("id") == row["id"] or r.get("username") == row["username"]:
                rows[i] = row
                found = True
                break
        if not found:
            rows.append(row)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as e:
        print("save_user_json:", e)


def delete_user_json(user_id: str) -> None:
    try:
        path = _json_path()
        if not path.exists():
            return
        rows = json.loads(path.read_text(encoding="utf-8") or "[]")
        rows = [r for r in rows if r.get("id") != user_id]
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as e:
        print("delete_user_json:", e)


def load_users_json() -> List[dict]:
    try:
        path = _json_path()
        if not path.exists():
            return []
        rows = json.loads(path.read_text(encoding="utf-8") or "[]")
        return rows if isinstance(rows, list) else []
    except Exception as e:
        print("load_users_json:", e)
        return []


def save_user_supabase(user) -> bool:
    """Write user via PostgREST (works even when supabase-py path is flaky)."""
    url, key = _supabase_creds()
    if not url or not key:
        print("save_user_supabase: missing SUPABASE_URL or SUPABASE_KEY")
        return False

    row = _user_to_dict(user)
    endpoint = url + "/rest/v1/app_users"
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    # Prefer httpx, fall back to urllib
    try:
        import httpx
        r = httpx.post(endpoint, headers=headers, json=row, timeout=20.0)
        if r.status_code in (200, 201):
            print("save_user_supabase REST OK:", row["username"], r.status_code)
            return True
        # retry with upsert on conflict via on_conflict=username
        r2 = httpx.post(
            endpoint + "?on_conflict=username",
            headers=headers,
            json=row,
            timeout=20.0,
        )
        if r2.status_code in (200, 201):
            print("save_user_supabase REST on_conflict OK:", row["username"])
            return True
        print(
            "save_user_supabase REST failed:",
            r.status_code, r.text[:300],
            "|", r2.status_code, r2.text[:300],
        )
    except Exception as e:
        print("save_user_supabase httpx:", e)
        try:
            import urllib.request

            req = urllib.request.Request(
                endpoint,
                data=json.dumps(row).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                print("save_user_supabase urllib OK:", row["username"], resp.status)
                return True
        except Exception as e2:
            print("save_user_supabase urllib:", e2)

    # Last resort: supabase-py client
    try:
        from app.db import use_db, client
        if use_db():
            sb = client()
            sb.table("app_users").upsert(row).execute()
            print("save_user_supabase py client OK:", row["username"])
            return True
    except Exception as e:
        print("save_user_supabase py client:", e)
    return False


def delete_user_supabase(user_id: str) -> bool:
    url, key = _supabase_creds()
    if not url or not key:
        return False
    endpoint = url + "/rest/v1/app_users?id=eq." + str(user_id)
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
    }
    try:
        import httpx
        r = httpx.delete(endpoint, headers=headers, timeout=15.0)
        return r.status_code in (200, 204)
    except Exception as e:
        print("delete_user_supabase:", e)
        try:
            from app.db import sb_delete
            return bool(sb_delete("app_users", user_id))
        except Exception:
            return False


def load_users_supabase() -> List[dict]:
    url, key = _supabase_creds()
    if not url or not key:
        return []
    endpoint = url + "/rest/v1/app_users?select=*&order=username"
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
    }
    try:
        import httpx
        r = httpx.get(endpoint, headers=headers, timeout=20.0)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
        print("load_users_supabase REST:", r.status_code, r.text[:200])
    except Exception as e:
        print("load_users_supabase:", e)
    try:
        from app.db import use_db, sb_select
        if use_db():
            return sb_select("app_users", order="username") or []
    except Exception as e:
        print("load_users_supabase py:", e)
    return []


def persist_user(user) -> None:
    ok = save_user_supabase(user)
    save_user_json(user)
    if ok:
        print("persist_user: %s → Supabase + JSON" % user.username)
    else:
        print("persist_user: %s → JSON only (Supabase write failed)" % user.username)


def remove_user(user_id: str) -> None:
    delete_user_supabase(user_id)
    delete_user_json(user_id)


def load_all_user_rows() -> List[dict]:
    rows = load_users_supabase()
    if rows:
        print("load_all_user_rows: %d from Supabase" % len(rows))
        return rows
    rows = load_users_json()
    if rows:
        print("load_all_user_rows: %d from JSON" % len(rows))
    return rows


def hydrate_auth_users() -> int:
    from app import auth

    rows = load_all_user_rows()
    if not rows:
        return 0

    auth._USERS.clear()
    auth._BY_USERNAME.clear()
    for r in rows:
        perms = r.get("permissions") or []
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except Exception:
                perms = []
        try:
            user = auth.User(
                id=str(r["id"]),
                username=str(r["username"]),
                full_name=str(r.get("full_name") or r["username"]),
                role=str(r.get("role") or "observer"),
                password_hash=str(r["password_hash"]),
                salt=str(r["salt"]),
                active=bool(r.get("active", True)),
                permissions=set(perms),
                created_at=str(r.get("created_at") or ""),
                created_by=str(r.get("created_by") or ""),
            )
            auth._USERS[user.id] = user
            auth._BY_USERNAME[user.username] = user.id
        except Exception as e:
            print("hydrate skip row:", e)
    return len(auth._USERS)


def sync_all_memory_users_to_supabase() -> dict:
    """Push every in-memory user to Supabase. Returns counts."""
    from app.auth import list_users

    ok, fail = [], []
    for u in list_users():
        if save_user_supabase(u):
            save_user_json(u)
            ok.append(u.username)
        else:
            fail.append(u.username)
    return {"saved": ok, "failed": fail, "saved_count": len(ok), "failed_count": len(fail)}


def patch_auth_persistence() -> None:
    from app import auth

    if getattr(auth, "_persistence_patched", False):
        return

    _orig_create = auth.create_user
    _orig_update = auth.update_user
    _orig_delete = auth.delete_user

    def create_user(*args, **kwargs):
        u = _orig_create(*args, **kwargs)
        try:
            persist_user(u)
        except Exception as e:
            print("create_user persist:", e)
        return u

    def update_user(user_id, **kwargs):
        u = _orig_update(user_id, **kwargs)
        if u:
            try:
                persist_user(u)
            except Exception as e:
                print("update_user persist:", e)
        return u

    def delete_user(user_id):
        ok = _orig_delete(user_id)
        if ok:
            try:
                remove_user(user_id)
            except Exception as e:
                print("delete_user persist:", e)
        return ok

    auth.create_user = create_user
    auth.update_user = update_user
    auth.delete_user = delete_user
    auth._persistence_patched = True
    print("user_store: persistence enabled")
