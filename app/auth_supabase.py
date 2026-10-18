"""Back-compat wrappers — real logic lives in app.user_store."""
from __future__ import annotations


def hydrate_users_from_supabase() -> int:
    try:
        from app.user_store import hydrate_auth_users, patch_auth_persistence
        # Ensure create/update/delete already persist before any seed
        patch_auth_persistence()
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
        from app.user_store import patch_auth_persistence, persist_user
        from app.auth import list_users
        patch_auth_persistence()
        # If we only have seed users in memory, write them out now
        for u in list_users():
            try:
                persist_user(u)
            except Exception as e:
                print("seed persist:", e)
    except Exception as e:
        print("patch_auth_for_supabase:", e)
