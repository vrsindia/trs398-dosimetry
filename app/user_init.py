"""Called from bootstrap: load and persist users."""
import traceback


def init_users():
    try:
        from app.user_store import patch_auth_persistence, hydrate_auth_users, persist_user
        from app.auth import seed_users, list_users
        patch_auth_persistence()
        n = hydrate_auth_users()
        if n:
            print("Loaded %d users from store (Supabase/JSON)" % n)
            return n
        seed_users()
        for u in list_users():
            try:
                persist_user(u)
            except Exception as e:
                print("seed persist:", e)
        print("seed_users + persist (%d users)" % len(list_users()))
        return len(list_users())
    except Exception as e:
        print("init_users:", e)
        traceback.print_exc()
        try:
            from app.auth import seed_users
            seed_users()
        except Exception:
            pass
        return 0
