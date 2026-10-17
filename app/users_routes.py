"""User directory with clear section labels and grid permissions."""
from __future__ import annotations
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    get_user_by_token, list_users, create_user, update_user, delete_user,
    ROLES, SECTION_LABELS, PERM_LABELS, ALL_SECTION_PERMS,
    PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
    PERM_ADMIN_PANEL,
)

COOKIE = "dosepro_session"

SYSTEM_PERMS = [
    PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
    PERM_ADMIN_PANEL,
]


def register_users_routes(app, templates):
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in ("/users", "/users/add")
        and not str(getattr(r, "path", "")).startswith("/users/{")
    ]

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _require_admin(request: Request):
        user = _user(request)
        if not user:
            return None
        role = (user.role or "").lower()
        if role not in ("developer", "admin") and not user.has(PERM_USER_MANAGE):
            return None
        return user

    def _ctx(request, user, message="", error=""):
        return {
            "request": request,
            "current_user": user,
            "users": list_users(),
            "roles": list(ROLES),
            "section_perms": list(ALL_SECTION_PERMS),
            "section_labels": dict(SECTION_LABELS),
            "system_perms": list(SYSTEM_PERMS),
            "perm_labels": dict(PERM_LABELS),
            "message": message,
            "error": error,
        }

    def _tpl(request, **ctx):
        try:
            return templates.TemplateResponse(
                request=request, name="users.html", context=ctx,
            )
        except TypeError:
            ctx["request"] = request
            return templates.TemplateResponse("users.html", ctx)

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
            create_user(username, password, full_name, role, created_by=user.username)
            return RedirectResponse("/users?msg=User+created", 303)
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
        perms = form.getlist("permissions") if hasattr(form, "getlist") else []
        kwargs = {
            "full_name": full_name,
            "role": role,
            "active": active,
            "permissions": set(perms),
        }
        if password.strip():
            kwargs["password"] = password.strip()
        try:
            update_user(uid, **kwargs)
            return RedirectResponse("/users?msg=User+updated", 303)
        except Exception as e:
            return _tpl(request, **_ctx(request, user, error=str(e)))

    @app.post("/users/{uid}/delete")
    async def users_delete(request: Request, uid: str):
        user = _require_admin(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            delete_user(uid)
            return RedirectResponse("/users?msg=User+deleted", 303)
        except Exception as e:
            return _tpl(request, **_ctx(request, user, error=str(e)))

    print("users_routes: section grid registered")
    return True
