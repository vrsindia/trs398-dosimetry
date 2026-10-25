"""User directory — collapsible cards with section + task tick boxes.
Always persist create/update/delete to Supabase + JSON (do not rely on import-time patch).
"""
from __future__ import annotations
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app import auth as auth_mod
from app.auth import (
    get_user_by_token, list_users,
    ROLES, SECTION_LABELS, PERM_LABELS, ALL_SECTION_PERMS,
    PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
    PERM_ADMIN_PANEL,
)

COOKIE = "dosepro_session"
TEMPLATE = "users_dir.html"

SYSTEM_PERMS = [
    PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
    PERM_ADMIN_PANEL,
]

SECTION_PERMS = list(ALL_SECTION_PERMS)


def _persist(user) -> str:
    """Force-save user; return short status for UI."""
    try:
        from app.user_store import persist_user, save_user_supabase
        from app.db import use_db, status as db_status
        persist_user(user)
        st = db_status()
        if st.get("using_database"):
            ok = save_user_supabase(user)
            if ok:
                return "saved_to_supabase"
            return "supabase_save_failed"
        return "saved_json_only_no_supabase_env"
    except Exception as e:
        print("users_routes _persist:", e)
        return "persist_error:%s" % e


def register_users_routes(app, templates):
    kept = []
    for r in app.router.routes:
        path = getattr(r, "path", None)
        if path in ("/users", "/users/add", "/users-db-status") or (
            isinstance(path, str) and path.startswith("/users/")
        ):
            continue
        kept.append(r)
    app.router.routes[:] = kept

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _require_admin(request: Request):
        user = _user(request)
        if not user:
            return None
        role = (getattr(user, "role", "") or "").lower()
        if role in ("developer", "admin"):
            return user
        try:
            if user.has(PERM_USER_MANAGE):
                return user
        except Exception:
            pass
        return None

    def _ctx(request, user, message="", error=""):
        users = list_users()
        for u in users:
            perms = getattr(u, "permissions", None)
            if not isinstance(perms, set):
                try:
                    u.permissions = set(perms or [])
                except Exception:
                    u.permissions = set()
        db_msg = ""
        try:
            from app.db import status as db_status
            st = db_status()
            if not st.get("using_database"):
                db_msg = (
                    " Warning: Supabase is not connected (set SUPABASE_URL and "
                    "SUPABASE_KEY=service_role on Render). Users will disappear after restart."
                )
        except Exception:
            pass
        return {
            "request": request,
            "current_user": user,
            "users": users,
            "roles": list(ROLES),
            "section_perms": SECTION_PERMS,
            "section_labels": dict(SECTION_LABELS),
            "system_perms": list(SYSTEM_PERMS),
            "perm_labels": dict(PERM_LABELS),
            "message": (message or "") + db_msg,
            "error": error,
        }

    def _tpl(request, **ctx):
        try:
            return templates.TemplateResponse(
                request=request, name=TEMPLATE, context=ctx,
            )
        except TypeError:
            ctx["request"] = request
            try:
                return templates.TemplateResponse(TEMPLATE, ctx)
            except TypeError:
                return templates.TemplateResponse(TEMPLATE, context=ctx)

    @app.get("/users-db-status")
    async def users_db_status(request: Request):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            from app.db import status as db_status, use_db
            from app.user_store import load_users_supabase, load_users_json
            st = db_status()
            sb_rows = load_users_supabase() if use_db() else []
            js_rows = load_users_json()
            return JSONResponse({
                **st,
                "memory_users": [u.username for u in list_users()],
                "supabase_users": [r.get("username") for r in (sb_rows or [])],
                "json_users": [r.get("username") for r in (js_rows or [])],
                "supabase_count": len(sb_rows or []),
                "json_count": len(js_rows or []),
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/users", response_class=HTMLResponse)
    async def users_page(request: Request):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(request, **_ctx(request, user, message=msg))

    @app.post("/users/add")
    async def users_add(
        request: Request,
        username: str = Form(...),
        full_name: str = Form(...),
        password: str = Form(...),
        role: str = Form(...),
    ):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            # Use module attribute so persistence patch (if any) is always used
            new_u = auth_mod.create_user(
                username, password, full_name, role,
                created_by=getattr(user, "username", "") or "",
            )
            status = _persist(new_u)
            if status == "saved_to_supabase":
                msg = "User+created+and+saved+to+Supabase"
            elif status == "saved_json_only_no_supabase_env":
                msg = "User+created+but+Supabase+not+configured+will+be+lost+on+restart"
            else:
                msg = "User+created+persist=" + status.replace(" ", "+")
            return RedirectResponse("/users?msg=" + msg, 303)
        except Exception as e:
            return _tpl(request, **_ctx(request, user, error=str(e)))

    @app.post("/users/{uid}/edit")
    async def users_edit(request: Request, uid: str):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        full_name = str(form.get("full_name") or "")
        role = str(form.get("role") or "physicist")
        password = str(form.get("password") or "")
        active = form.get("active") == "1"
        if hasattr(form, "getlist"):
            perms = form.getlist("permissions")
        else:
            raw = form.get("permissions")
            perms = raw if isinstance(raw, list) else ([raw] if raw else [])
        kwargs = {
            "full_name": full_name,
            "role": role,
            "active": active,
            "permissions": set(str(p) for p in perms if p),
        }
        if password.strip():
            kwargs["password"] = password.strip()
        try:
            updated = auth_mod.update_user(uid, **kwargs)
            if updated:
                _persist(updated)
            return RedirectResponse("/users?msg=User+updated", 303)
        except Exception as e:
            return _tpl(request, **_ctx(request, user, error=str(e)))

    @app.post("/users/{uid}/delete")
    async def users_delete(request: Request, uid: str):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            auth_mod.delete_user(uid)
            try:
                from app.user_store import remove_user
                remove_user(uid)
            except Exception as e:
                print("delete persist:", e)
            return RedirectResponse("/users?msg=User+deleted", 303)
        except Exception as e:
            return _tpl(request, **_ctx(request, user, error=str(e)))

    print("users_routes: collapsible users + explicit Supabase persist")
    return True
