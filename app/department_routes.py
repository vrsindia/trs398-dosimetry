"""Department view / edit / save, logo upload and delete."""
from __future__ import annotations
import base64
from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_DEPT_EDIT
from app.models import get_department, update_department

COOKIE = "dosepro_session"
MAX_LOGO_BYTES = 1024 * 1024  # 1 MB


def _strip_routes(app, paths):
    paths = set(paths)
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", None) not in paths
    ]


def register_department_routes(app, templates):
    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _can_edit(user) -> bool:
        if not user:
            return False
        role = (getattr(user, "role", "") or "").strip().lower()
        if role in ("developer", "admin"):
            return True
        try:
            return bool(user.has(PERM_DEPT_EDIT))
        except Exception:
            return False

    def _dept_object():
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
        except Exception as e:
            print("save_department db failed:", e)
        update_department(**data)

    _strip_routes(app, (
        "/department", "/department/edit",
        "/department/logo", "/department/logo/delete",
    ))

    @app.get("/department", response_class=HTMLResponse)
    async def dept_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        can_edit = _can_edit(user)
        saved = request.query_params.get("saved") == "1"
        logo_ok = request.query_params.get("logo") == "1"
        logo_del = request.query_params.get("logo_del") == "1"
        logo_err = request.query_params.get("logo_err") or ""
        force_view = request.query_params.get("view") == "1"
        show_form = can_edit and not force_view
        return templates.TemplateResponse(
            "department.html",
            {
                "request": request,
                "dept": _dept_object(),
                "current_user": user,
                "can_edit": can_edit,
                "show_form": show_form,
                "saved": saved,
                "logo_ok": logo_ok,
                "logo_del": logo_del,
                "logo_err": logo_err.replace("+", " "),
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
            notes=(notes or "").strip(),
            head_physicist="",
        )
        return RedirectResponse("/department?saved=1", 303)

    @app.post("/department/logo")
    async def dept_logo(request: Request, logo: UploadFile = File(None)):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        if not _can_edit(user):
            raise HTTPException(403, "Only developer or admin can upload the logo")
        if logo is None or not getattr(logo, "filename", None):
            return RedirectResponse("/department?logo_err=No+file+selected", 303)
        try:
            data = await logo.read()
        except Exception as e:
            return RedirectResponse(f"/department?logo_err=Read+failed:+{e}", 303)
        if not data:
            return RedirectResponse("/department?logo_err=Empty+file", 303)
        if len(data) > MAX_LOGO_BYTES:
            return RedirectResponse(
                f"/department?logo_err=Logo+must+be+≤+1+MB+(got+{len(data)//1024}+KB)",
                303,
            )
        content_type = (logo.content_type or "image/png").lower()
        # Accept common types; default to png if unknown
        allowed = {
            "image/png", "image/jpeg", "image/jpg", "image/svg+xml",
            "image/webp", "image/gif", "application/octet-stream",
        }
        if content_type not in allowed:
            # still try if extension looks like an image
            name = (logo.filename or "").lower()
            if not any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
                return RedirectResponse(
                    "/department?logo_err=Allowed+types:+PNG,+JPG,+SVG,+WebP",
                    303,
                )
            if name.endswith(".jpg") or name.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif name.endswith(".svg"):
                content_type = "image/svg+xml"
            elif name.endswith(".webp"):
                content_type = "image/webp"
            else:
                content_type = "image/png"
        try:
            b64 = base64.b64encode(data).decode("ascii")
            data_url = f"data:{content_type};base64,{b64}"
            _save_dept(logo_url=data_url)
        except Exception as e:
            return RedirectResponse(f"/department?logo_err=Save+failed:+{e}", 303)
        return RedirectResponse("/department?logo=1", 303)

    @app.post("/department/logo/delete")
    async def dept_logo_delete(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        if not _can_edit(user):
            raise HTTPException(403, "Only developer or admin can delete the logo")
        _save_dept(logo_url="")
        return RedirectResponse("/department?logo_del=1", 303)

    print("department routes active (edit/save/logo/delete)")
    return True
