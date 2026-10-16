"""Department admin edit with DB save (activity routes moved to utility_routes)."""

from __future__ import annotations
from typing import Optional

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token
from app.models import get_department, update_department
from app.db import use_db
from app import repo

COOKIE = "dosepro_session"


def register_activity_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    def _is_admin(user) -> bool:
        return user and user.role in ("developer", "admin")

    # Override department page + edit: admin/developer only for edit; save to DB
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) in ("/department", "/department/edit")]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/department", response_class=HTMLResponse)
    async def dept_page(request: Request):
        user = _user(request)
        if not user:
            return _login()
        if use_db():
            try:
                dept = repo.get_department()
            except Exception:
                dept = get_department()
        else:
            dept = get_department()
        can_edit = _is_admin(user)
        return templates.TemplateResponse(
            request=request, name="department.html",
            context={"dept": dept, "current_user": user, "can_edit": can_edit},
        )

    @app.post("/department/edit")
    async def dept_edit(
        request: Request,
        name: str = Form(""),
        hospital: str = Form(""),
        address: str = Form(""),
        city: str = Form(""),
        country: str = Form(""),
        phone: str = Form(""),
        email: str = Form(""),
        head_physicist: str = Form(""),
        notes: str = Form(""),
        requested_by: str = Form(""),
    ):
        user = _user(request)
        if not user:
            return _login()
        if not _is_admin(user):
            raise HTTPException(403, "Only Developer or Admin can edit department details")
        data = dict(
            name=name, hospital=hospital, address=address, city=city, country=country,
            phone=phone, email=email, head_physicist=head_physicist, notes=notes,
        )
        if use_db():
            try:
                repo.save_department(**data)
            except Exception:
                update_department(**data)
        else:
            update_department(**data)
        return RedirectResponse("/department", 303)

    return True
