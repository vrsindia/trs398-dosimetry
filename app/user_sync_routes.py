"""Always-on routes: user DB status + force sync all users to Supabase."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE = "dosepro_session"


def register_user_sync_routes(app, templates=None):
    from app.auth import get_user_by_token, list_users

    def _admin(request: Request):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user:
            return None
        if (getattr(user, "role", "") or "").lower() in ("developer", "admin"):
            return user
        try:
            if user.has("user_manage"):
                return user
        except Exception:
            pass
        return None

    # Drop old copies
    for path in ("/users-db-status", "/users/sync-to-supabase"):
        app.router.routes[:] = [
            r for r in list(app.router.routes)
            if getattr(r, "path", None) != path
        ]

    @app.get("/users-db-status")
    async def users_db_status(request: Request):
        if not _admin(request):
            return JSONResponse({"error": "login as developer/admin"}, status_code=401)
        import os
        from app.user_store import load_users_supabase, load_users_json, _supabase_creds

        url, key = _supabase_creds()
        sb_rows = load_users_supabase()
        js_rows = load_users_json()
        return JSONResponse({
            "supabase_url_set": bool(url),
            "supabase_key_set": bool(key),
            "key_looks_like_service_role": ("service_role" in key) or key.startswith("eyJ") and len(key) > 100,
            "memory_users": [u.username for u in list_users()],
            "supabase_users": [r.get("username") for r in (sb_rows or [])],
            "json_users": [r.get("username") for r in (js_rows or [])],
            "supabase_count": len(sb_rows or []),
            "json_count": len(js_rows or []),
        })

    @app.post("/users/sync-to-supabase")
    async def users_sync(request: Request):
        if not _admin(request):
            return RedirectResponse("/login", 303)
        from app.user_store import sync_all_memory_users_to_supabase

        result = sync_all_memory_users_to_supabase()
        msg = "Synced+%d+to+Supabase" % result.get("saved_count", 0)
        if result.get("failed_count"):
            msg += "+failed+" + "+".join(result.get("failed") or [])
        return RedirectResponse("/users?msg=" + msg, 303)

    @app.get("/users/sync-to-supabase")
    async def users_sync_get(request: Request):
        """Allow GET so you can open the URL in the browser."""
        if not _admin(request):
            return RedirectResponse("/login", 303)
        from app.user_store import sync_all_memory_users_to_supabase

        result = sync_all_memory_users_to_supabase()
        return JSONResponse(result)

    print("user_sync_routes: /users-db-status + /users/sync-to-supabase")
    return True
