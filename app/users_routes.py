"""User directory — safe collapsible cards, always persist to Supabase."""
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

_KEEP_PATHS = {"/users-db-status", "/users/sync-to-supabase"}


def _persist(user) -> str:
    try:
        from app.user_store import persist_user, save_user_supabase
        from app.db import status as db_status
        persist_user(user)
        st = db_status()
        if st.get("using_database"):
            ok = save_user_supabase(user)
            return "saved_to_supabase" if ok else "supabase_save_failed"
        return "saved_json_only_no_supabase_env"
    except Exception as e:
        print("users_routes _persist:", e)
        return "persist_error"


def _norm_perms(raw) -> set:
    if raw is None:
        return set()
    if isinstance(raw, set):
        return {str(x) for x in raw}
    if isinstance(raw, (list, tuple)):
        return {str(x) for x in raw}
    if isinstance(raw, str):
        try:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return {str(x) for x in parsed}
        except Exception:
            pass
        return {raw} if raw else set()
    try:
        return {str(x) for x in raw}
    except Exception:
        return set()


def register_users_routes(app, templates):
    kept = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        if path in _KEEP_PATHS:
            kept.append(r)
            continue
        if path in ("/users", "/users/add") or (
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

    def _ctx(user, message="", error=""):
        """Build template context. Do NOT include request here."""
        users = []
        try:
            users = list(list_users() or [])
        except Exception as e:
            print("list_users:", e)
            error = (error or "") + (" list_users error: " + str(e))

        for u in users:
            try:
                u.permissions = _norm_perms(getattr(u, "permissions", None))
            except Exception:
                try:
                    u.permissions = set()
                except Exception:
                    pass

        db_msg = ""
        try:
            from app.db import status as db_status
            st = db_status()
            if not st.get("using_database"):
                db_msg = (
                    " Warning: Supabase not connected — users may be lost on restart."
                )
        except Exception:
            pass

        return {
            "current_user": user,
            "users": users,
            "roles": list(ROLES),
            "section_perms": list(SECTION_PERMS),
            "section_labels": dict(SECTION_LABELS),
            "system_perms": list(SYSTEM_PERMS),
            "perm_labels": dict(PERM_LABELS),
            "message": ((message or "") + db_msg).strip(),
            "error": error or "",
        }

    def _tpl(request: Request, ctx: dict):
        """Render users template. request only once."""
        context = dict(ctx)
        context.pop("request", None)
        try:
            return templates.TemplateResponse(
                request=request, name=TEMPLATE, context=context,
            )
        except TypeError:
            context["request"] = request
            try:
                return templates.TemplateResponse(TEMPLATE, context)
            except TypeError:
                try:
                    return templates.TemplateResponse(TEMPLATE, context=context)
                except Exception as e:
                    print("users template error:", e)
                    return HTMLResponse(
                        "<h1>Users</h1><p>Template error: %s</p><p><a href='/'>Home</a></p>" % e,
                        status_code=500,
                    )
        except Exception as e:
            print("users template error:", e)
            return HTMLResponse(
                "<h1>Users</h1><p>Template error: %s</p><p><a href='/'>Home</a></p>" % e,
                status_code=500,
            )

    @app.get("/users", response_class=HTMLResponse)
    async def users_page(request: Request):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        try:
            return _tpl(request, _ctx(user, message=msg))
        except Exception as e:
            print("users_page error:", e)
            import traceback
            traceback.print_exc()
            return HTMLResponse(
                "<h1>Users error</h1><pre>%s</pre><a href='/'>Home</a>" % e,
                status_code=500,
            )

    @app.post("/users/add")
    async def users_add(
        request: Request,
        username: str = Form(""),
        full_name: str = Form(""),
        password: str = Form(""),
        role: str = Form("physicist"),
    ):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            new_u = auth_mod.create_user(
                str(username).strip(),
                str(password),
                str(full_name).strip() or str(username).strip(),
                str(role).strip() or "physicist",
                created_by=getattr(user, "username", "") or "",
            )
            status = _persist(new_u)
            msg = "User+created"
            if status == "saved_to_supabase":
                msg = "User+created+and+saved+to+Supabase"
            elif "json_only" in status:
                msg = "User+created+but+Supabase+not+configured"
            return RedirectResponse("/users?msg=" + msg, 303)
        except Exception as e:
            return _tpl(request, _ctx(user, error=str(e)))

    @app.post("/users/{uid}/edit")
    async def users_edit(request: Request, uid: str):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            form = await request.form()
            full_name = str(form.get("full_name") or "")
            role = str(form.get("role") or "physicist")
            password = str(form.get("password") or "")
            active = str(form.get("active") or "") in ("1", "on", "true", "True")
            if hasattr(form, "getlist"):
                perms = form.getlist("permissions")
            else:
                raw = form.get("permissions")
                perms = raw if isinstance(raw, list) else ([raw] if raw else [])
            kwargs = {
                "full_name": full_name,
                "role": role,
                "active": active,
                "permissions": _norm_perms(perms),
            }
            if password.strip():
                kwargs["password"] = password.strip()
            updated = auth_mod.update_user(uid, **kwargs)
            if updated:
                _persist(updated)
            return RedirectResponse("/users?msg=User+updated", 303)
        except Exception as e:
            print("users_edit error:", e)
            import traceback
            traceback.print_exc()
            return _tpl(request, _ctx(user, error=str(e)))

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
            return _tpl(request, _ctx(user, error=str(e)))

    print("users_routes: safe users page registered")
    return True
