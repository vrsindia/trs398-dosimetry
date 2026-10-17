"""Load / sync users with Supabase when configured."""
from __future__ import annotations


def hydrate_users_from_supabase() -> int:
    """If Supabase has app_users, load them into in-memory auth store.
    Returns number of users loaded. Falls back to seed_users if empty.
    """
    try:
        from app.db import use_db
        if not use_db():
            return 0
        from app.repo_extra import load_users_from_db
        from app import auth
        rows = load_users_from_db()
        if not rows:
            return 0
        # Clear memory and load
        auth._USERS.clear()
        auth._BY_USERNAME.clear()
        for r in rows:
            perms = r.get("permissions") or []
            if isinstance(perms, str):
                import json
                try:
                    perms = json.loads(perms)
                except Exception:
                    perms = []
            user = auth.User(
                id=r["id"],
                username=r["username"],
                full_name=r.get("full_name") or r["username"],
                role=r.get("role") or "observer",
                password_hash=r["password_hash"],
                salt=r["salt"],
                active=bool(r.get("active", True)),
                permissions=set(perms),
                created_at=r.get("created_at") or "",
                created_by=r.get("created_by") or "",
            )
            auth._USERS[user.id] = user
            auth._BY_USERNAME[user.username] = user.id
        return len(rows)
    except Exception as e:
        print("hydrate_users_from_supabase:", e)
        return 0


def sync_user_to_supabase(user) -> None:
    try:
        from app.repo_extra import save_user_row
        save_user_row(user)
    except Exception as e:
        print("sync_user_to_supabase:", e)


def patch_auth_for_supabase():
    """Wrap create_user / update_user / delete_user to persist."""
    try:
        from app import auth
        from app.db import use_db
        if not use_db():
            return

        _orig_create = auth.create_user
        _orig_update = auth.update_user
        _orig_delete = auth.delete_user

        def create_user(*args, **kwargs):
            u = _orig_create(*args, **kwargs)
            sync_user_to_supabase(u)
            return u

        def update_user(user_id, **kwargs):
            u = _orig_update(user_id, **kwargs)
            if u:
                sync_user_to_supabase(u)
            return u

        def delete_user(user_id):
            ok = _orig_delete(user_id)
            if ok:
                try:
                    from app.repo_extra import delete_user_row
                    delete_user_row(user_id)
                except Exception:
                    pass
            return ok

        auth.create_user = create_user
        auth.update_user = update_user
        auth.delete_user = delete_user
        print("auth_supabase: create/update/delete patched")
    except Exception as e:
        print("patch_auth_for_supabase:", e)
