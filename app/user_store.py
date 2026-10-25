"""Persistent user store: Supabase (preferred) + local JSON backup."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

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
    """Upsert user into public.app_users. Returns True on success."""
    try:
        from app.db import use_db, client
        if not use_db():
            print("save_user_supabase: use_db() is False — check SUPABASE_URL and SUPABASE_KEY")
            return False
        sb = client()
        if not sb:
            print("save_user_supabase: no client")
            return False
        row = _user_to_dict(user)
        # Try upsert first
        try:
            res = sb.table("app_users").upsert(row).execute()
            print("save_user_supabase upsert OK:", row.get("username"), "data=", bool(res.data))
            return True
        except Exception as e1:
            print("save_user_supabase upsert failed:", e1)
            # Fallback: insert
            try:
                res = sb.table("app_users").insert(row).execute()
                print("save_user_supabase insert OK:", row.get("username"))
                return True
            except Exception as e2:
                print("save_user_supabase insert failed:", e2)
                # Fallback: update by username
                try:
                    res = (
                        sb.table("app_users")
                        .update(row)
                        .eq("username", row["username"])
                        .execute()
                    )
                    print("save_user_supabase update OK:", row.get("username"))
                    return True
                except Exception as e3:
                    print("save_user_supabase all methods failed:", e3)
                    return False
    except Exception as e:
        print("save_user_supabase:", e)
        return False


def delete_user_supabase(user_id: str) -> bool:
    try:
        from app.db import use_db, sb_delete
        if not use_db():
            return False
        return bool(sb_delete("app_users", user_id))
    except Exception as e:
        print("delete_user_supabase:", e)
        return False


def load_users_supabase() -> List[dict]:
    try:
        from app.db import use_db, sb_select
        if not use_db():
            return []
        return sb_select("app_users", order="username") or []
    except Exception as e:
        print("load_users_supabase:", e)
        return []


def persist_user(user) -> None:
    ok = save_user_supabase(user)
    save_user_json(user)
    if ok:
        print("persist_user: %s → Supabase + JSON" % user.username)
    else:
        print(
            "persist_user: %s → JSON only (Supabase not saving — check env + logs)"
            % user.username
        )


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
    print("user_store: create/update/delete persistence enabled")
