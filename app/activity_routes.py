"""Source activity calculator + department admin edit with DB save."""

from __future__ import annotations
from datetime import date
from typing import Optional

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_CALCULATE, PERM_DEPT_EDIT
from app.calculations.activity import calculate_activity, list_sources
from app.models import get_department, update_department, submit_change
from app.db import use_db
from app import repo

COOKIE = "dosepro_session"
UNITS = ["Ci", "mCi", "uCi", "Bq", "MBq", "GBq"]


def register_activity_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    def _is_admin(user) -> bool:
        return user and user.role in ("developer", "admin")

    @app.get("/activity", response_class=HTMLResponse)
    async def activity_page(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "sources": list_sources(),
                "units": UNITS,
                "result": None,
                "error": None,
                "inputs": None,
                "today": date.today().isoformat(),
                "current_user": user,
            },
        )

    @app.post("/activity", response_class=HTMLResponse)
    async def activity_calc(
        request: Request,
        source: str = Form(...),
        activity: float = Form(...),
        unit: str = Form("Ci"),
        output_unit: str = Form("Ci"),
        mode: str = Form("days"),
        days: Optional[float] = Form(None),
        reference_date: Optional[str] = Form(None),
        calculation_date: Optional[str] = Form(None),
    ):
        user = _user(request)
        if not user:
            return _login()
        inputs = {
            "source": source, "activity": activity, "unit": unit,
            "output_unit": output_unit, "mode": mode,
            "days": days, "reference_date": reference_date or "",
            "calculation_date": calculation_date or "",
        }
        error = None
        result = None
        try:
            if mode == "dates":
                result = calculate_activity(
                    source, activity, unit,
                    reference_date=reference_date,
                    calculation_date=calculation_date,
                    output_unit=output_unit,
                )
            else:
                if days is None:
                    raise ValueError("Days is required")
                result = calculate_activity(
                    source, activity, unit,
                    days=float(days),
                    output_unit=output_unit,
                )
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "sources": list_sources(),
                "units": UNITS,
                "result": result,
                "error": error,
                "inputs": inputs,
                "today": date.today().isoformat(),
                "current_user": user,
            },
        )

    # Override department page + edit: admin/developer only for edit; save to DB
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) in ("/department", "/department/edit")
                 and ("GET" in (getattr(r, "methods", set()) or set())
                      or "POST" in (getattr(r, "methods", set()) or set()))]
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
        # load from DB if available
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
        # Direct save for admin (no approval queue)
        if use_db():
            try:
                repo.save_department(**data)
            except Exception:
                update_department(**data)
        else:
            update_department(**data)
        return RedirectResponse("/department", 303)

    return True
