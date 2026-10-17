"""Department edit and logo upload — admin/developer only, direct save (no approval)."""
from __future__ import annotations
import base64
from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import get_user_by_token, PERM_DEPT_EDIT
from app.models import get_department, update_department

COOKIE = "dosepro_session"
MAX_LOGO_BYTES = 512 * 1024


def register_department_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _can_edit(user) -> bool:
        if not user:
            return False
        if getattr(user, "role", "") in ("developer", "admin"):
            return True
        return bool(user.has(PERM_DEPT_EDIT))

    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/department"
                 and "GET" in (getattr(r, "methods", set()) or set())]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/department", response_class=HTMLResponse)
    async def dept_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        return templates.TemplateResponse(
            request=request, name="department.html",
            context={
                "dept": get_department(),
                "current_user": user,
                "can_edit": _can_edit(user),
            },
        )

    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/department/edit"
                 and "POST" in (getattr(r, "methods", set()) or set())]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

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
    ):
        user = _user(request)
        if not _can_edit(user):
            return RedirectResponse("/login", 303)
        update_department(
            name=name, hospital=hospital, address=address, city=city,
            country=country, phone=phone, email=email,
            head_physicist=head_physicist, notes=notes,
        )
        return RedirectResponse("/department", 303)

    @app.post("/department/logo")
    async def dept_logo(request: Request, logo: UploadFile = File(...)):
        user = _user(request)
        if not _can_edit(user):
            return RedirectResponse("/login", 303)
        data = await logo.read()
        if len(data) > MAX_LOGO_BYTES:
            raise HTTPException(400, f"Logo must be ≤ 512 KB (got {len(data) // 1024} KB)")
        content_type = logo.content_type or "image/png"
        if content_type not in (
            "image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp",
        ):
            raise HTTPException(400, "Allowed types: PNG, JPG, SVG, WebP")
        b64 = base64.b64encode(data).decode("ascii")
        data_url = f"data:{content_type};base64,{b64}"
        update_department(logo_url=data_url)
        return RedirectResponse("/department", 303)

    return True
