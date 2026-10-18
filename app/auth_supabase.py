"""Back-compat wrappers — real logic lives in app.user_store."""
from __future__ import annotations


def hydrate_users_from_supabase() -> int:
    try:
        from app.user_store import hydrate_auth_users
        return hydrate_auth_users()
    except Exception as e:
        print("hydrate_users_from_supabase:", e)
        return 0


def sync_user_to_supabase(user) -> None:
    try:
        from app.user_store import persist_user
        persist_user(user)
    except Exception as e:
        print("sync_user_to_supabase:", e)


def patch_auth_for_supabase():
    try:
        from app.user_store import patch_auth_persistence
        patch_auth_persistence()
    except Exception as e:
        print("patch_auth_for_supabase:", e)
