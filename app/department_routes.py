"""Department view / edit / save and logo upload.
Admin and developer can edit and save directly (no approval queue).
"""
from __future__ import annotations
import base64
from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_DEPT_EDIT
from app.models import get_department, update_department

COOKIE = "dosepro_session"
MAX_LOGO_BYTES = 512 * 1024


def register_department_routes(app, templates):
    """Register (or re-register) department routes so they always win."""

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _can_edit(user) -> bool:
        if not user:
            return False
        if getattr(user, "role", "") in ("developer", "admin"):
            return True
        try:
            return bool(user.has(PERM_DEPT_EDIT))
        except Exception:
            return False

    def _dept_object():
        """Prefer DB department when available, else in-memory."""
        try:
            from app.db import use_db
            from app import repo
            if use_db():
                return repo.get_department()
        except Exception:
            pass
        return get_department()

    def _save_dept(**data):
        try:
            from app.db import use_db
            from app import repo
            if use_db():
                repo.save_department(**data)
                return
        except Exception:
            pass
        update_department(**data)

    # Remove any previous department routes so ours are the only ones
    for path in ("/department", "/department/edit", "/department/logo"):
        for r in list(app.router.routes):
            if getattr(r, "path", None) == path:
                try:
                    app.router.routes.remove(r)
                except ValueError:
                    pass

    @app.get("/department", response_class=HTMLResponse)
    async def dept_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        saved = request.query_params.get("saved") == "1"
        logo_ok = request.query_params.get("logo") == "1"
        edit = request.query_params.get("edit") == "1"
        can_edit = _can_edit(user)
        # Open in edit mode only when allowed and ?edit=1
        show_form = can_edit and edit
        return templates.TemplateResponse(
            request=request,
            name="department.html",
            context={
                "dept": _dept_object(),
                "current_user": user,
                "can_edit": can_edit,
                "show_form": show_form,
                "saved": saved,
                "logo_ok": logo_ok,
            },
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
    ):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        if not _can_edit(user):
            raise HTTPException(403, "Only developer or admin can edit department details")
        _save_dept(
            name=(name or "").strip(),
            hospital=(hospital or "").strip(),
            address=(address or "").strip(),
            city=(city or "").strip(),
            country=(country or "").strip(),
            phone=(phone or "").strip(),
            email=(email or "").strip(),
            head_physicist=(head_physicist or "").strip(),
            notes=(notes or "").strip(),
        )
        return RedirectResponse("/department?saved=1", 303)

    @app.post("/department/logo")
    async def dept_logo(request: Request, logo: UploadFile = File(...)):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        if not _can_edit(user):
            raise HTTPException(403, "Only developer or admin can upload the logo")
        data = await logo.read()
        if len(data) > MAX_LOGO_BYTES:
            raise HTTPException(400, f"Logo must be ≤ 512 KB (got {len(data) // 1024} KB)")
        content_type = (logo.content_type or "image/png").lower()
        if content_type not in (
            "image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp",
        ):
            raise HTTPException(400, "Allowed types: PNG, JPG, SVG, WebP")
        b64 = base64.b64encode(data).decode("ascii")
        data_url = f"data:{content_type};base64,{b64}"
        _save_dept(logo_url=data_url)
        return RedirectResponse("/department?logo=1", 303)

    return True
