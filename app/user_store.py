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
        "permissions": list(perms),
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


def load_users_json() -> List[dict]:
    try:
        data = json.loads(_json_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        print("load_users_json:", e)
        return []


def save_user_json(user) -> None:
    row = _user_to_dict(user)
    rows = load_users_json()
    out = []
    replaced = False
    for r in rows:
        if r.get("id") == row["id"] or r.get("username") == row["username"]:
            out.append(row)
            replaced = True
        else:
            out.append(r)
    if not replaced:
        out.append(row)
    try:
        _json_path().write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception as e:
        print("save_user_json:", e)


def save_user_supabase(user) -> bool:
    """Write user via PostgREST (works even when supabase-py path is flaky)."""
    url, key = _supabase_creds()
    if not url or not key:
        print("save_user_supabase: missing SUPABASE_URL or SUPABASE_KEY")
        return False
    row = _user_to_dict(user)
    # permissions as JSON array string for jsonb columns if needed — send as list
    endpoint = url + "/rest/v1/app_users"
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    # Prefer upsert on username or id
    try:
        import httpx
        # Try upsert with on_conflict=username
        r = httpx.post(
            endpoint + "?on_conflict=username",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row,
            timeout=20.0,
        )
        if r.status_code in (200, 201, 204):
            print("save_user_supabase REST OK:", row["username"], r.status_code)
            return True
        # Fallback without on_conflict
        r2 = httpx.post(endpoint, headers=headers, json=row, timeout=20.0)
        if r2.status_code in (200, 201, 204):
            print("save_user_supabase REST on_conflict OK:", row["username"])
            return True
        # PATCH by username
        r3 = httpx.patch(
            endpoint + "?username=eq." + row["username"],
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=row,
            timeout=20.0,
        )
        if r3.status_code in (200, 204):
            print("save_user_supabase REST PATCH OK:", row["username"])
            return True
        print("save_user_supabase REST failed:", r.status_code, r.text[:300], r2.status_code, r2.text[:200])
    except Exception as e:
        print("save_user_supabase httpx:", e)
        try:
            import urllib.request
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(row).encode("utf-8"),
                headers={
                    "apikey": key,
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                print("save_user_supabase urllib OK:", row["username"], resp.status)
                return True
        except Exception as e2:
            print("save_user_supabase urllib:", e2)
    try:
        from app.db import use_db, get_client
        if use_db():
            sb = get_client()
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
    try:
        import httpx
        r = httpx.delete(
            url + "/rest/v1/app_users?id=eq." + str(user_id),
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=15.0,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print("delete_user_supabase:", e)
        return False


def load_users_supabase() -> List[dict]:
    url, key = _supabase_creds()
    if not url or not key:
        print("load_users_supabase: no credentials")
        return []
    endpoint = url + "/rest/v1/app_users?select=*&order=username"
    headers = {"apikey": key, "Authorization": "Bearer " + key}
    try:
        import httpx
        r = httpx.get(endpoint, headers=headers, timeout=20.0)
        if r.status_code == 200:
            data = r.json()
            rows = data if isinstance(data, list) else []
            print("load_users_supabase REST: %d rows" % len(rows))
            return rows
        print("load_users_supabase REST:", r.status_code, r.text[:300])
    except Exception as e:
        print("load_users_supabase:", e)
    try:
        from app.db import use_db, sb_select
        if use_db():
            rows = sb_select("app_users", order="username") or []
            print("load_users_supabase py: %d rows" % len(rows))
            return rows
    except Exception as e:
        print("load_users_supabase py:", e)
    return []


def persist_user(user) -> bool:
    ok = save_user_supabase(user)
    try:
        save_user_json(user)
    except Exception:
        pass
    if ok:
        print("persist_user: %s → Supabase + JSON" % user.username)
    else:
        print("persist_user: %s → JSON only (Supabase write failed)" % user.username)
    return ok


def remove_user(user_id: str) -> None:
    delete_user_supabase(user_id)
    rows = [r for r in load_users_json() if str(r.get("id")) != str(user_id)]
    try:
        _json_path().write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_all_user_rows() -> List[dict]:
    rows = load_users_supabase()
    if rows:
        print("load_all_user_rows: %d from Supabase" % len(rows))
        return rows
    rows = load_users_json()
    if rows:
        print("load_all_user_rows: %d from JSON" % len(rows))
    return rows


def _row_to_user(r: dict):
    """Build auth.User from a DB/JSON row; tolerant of missing fields."""
    from app import auth
    import uuid

    perms = r.get("permissions") or []
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except Exception:
            perms = []
    if not isinstance(perms, (list, set, tuple)):
        perms = []

    uid = str(r.get("id") or uuid.uuid4())
    username = str(r.get("username") or "").strip().lower()
    if not username:
        raise ValueError("row missing username")

    password_hash = str(r.get("password_hash") or "")
    salt = str(r.get("salt") or "")
    # Allow display even if hash missing (user cannot log in until reset)
    if not password_hash:
        password_hash = "!"
    if not salt:
        salt = "0"

    return auth.User(
        id=uid,
        username=username,
        full_name=str(r.get("full_name") or username),
        role=str(r.get("role") or "observer"),
        password_hash=password_hash,
        salt=salt,
        active=bool(r.get("active", True)),
        permissions=set(str(p) for p in perms),
        created_at=str(r.get("created_at") or ""),
        created_by=str(r.get("created_by") or ""),
    )


def hydrate_auth_users() -> int:
    """Reload ALL users from Supabase (or JSON) into auth memory."""
    from app import auth

    rows = load_all_user_rows()
    if not rows:
        print("hydrate_auth_users: no rows")
        return 0

    auth._USERS.clear()
    auth._BY_USERNAME.clear()
    loaded = 0
    for r in rows:
        try:
            user = _row_to_user(r)
            auth._USERS[user.id] = user
            auth._BY_USERNAME[user.username] = user.id
            loaded += 1
        except Exception as e:
            print("hydrate skip row:", r.get("username"), e)
    print("hydrate_auth_users: loaded %d / %d" % (loaded, len(rows)))
    return loaded


def sync_all_memory_users_to_supabase() -> dict:
    from app.auth import list_users
    saved = 0
    failed = 0
    for u in list_users():
        if persist_user(u):
            saved += 1
        else:
            failed += 1
    return {"saved_count": saved, "failed_count": failed}


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
    print("patch_auth_persistence: create/update/delete → Supabase")
