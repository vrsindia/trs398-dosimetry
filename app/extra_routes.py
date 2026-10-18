"""Extra routes: calc profiles, reports PDF, energy calculate/save."""

from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from typing import Optional
from datetime import datetime, date

from app.models import (
    list_calc_profiles, add_calc_profile, update_calc_profile, CalcProfile,
    get_default_calc_profile, list_linacs, get_linac, get_beam, get_detector, list_detectors,
    find_tolerance, list_reports, get_report, list_output_records, add_output_record,
    OutputRecord, _new_id,
)
from app.reports import create_report_from_date, build_report_pdf
from app.auth import get_user_by_token, PERM_HISTORY_VIEW, PERM_CALCULATE

COOKIE = "dosepro_session"


def register_extra_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    def _require(request: Request, perm=None):
        user = _user(request)
        if not user:
            return None
        if perm and not user.has(perm):
            return None
        return user

    @app.post("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
    async def session_energy_calc(request: Request, sid: str, bid: str):
        user = _user(request)
        if not user:
            return _login()
        # Delegate to existing core handler if present; otherwise redirect
        return RedirectResponse(f"/session/{sid}", 303)

    @app.get("/calc-profiles", response_class=HTMLResponse)
    async def calc_profiles(request: Request):
        user = _user(request)
        if not user:
            return _login()
        try:
            profiles = list_calc_profiles()
        except Exception:
            profiles = []
        try:
            return templates.TemplateResponse(
                request=request, name="calc_profiles.html",
                context={"profiles": profiles, "current_user": user},
            )
        except Exception:
            return HTMLResponse("<h1>Calc profiles</h1>")

    @app.post("/calc-profiles/add")
    async def calc_profiles_add(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        try:
            p = CalcProfile(
                id=_new_id(),
                name=str(form.get("name") or "Profile"),
                notes=str(form.get("notes") or ""),
            )
            add_calc_profile(p)
        except Exception as e:
            print("calc profile add:", e)
        return RedirectResponse("/calc-profiles", 303)

    @app.post("/calc-profiles/{pid}/edit")
    async def calc_profiles_edit(request: Request, pid: str):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        try:
            update_calc_profile(
                pid,
                name=str(form.get("name") or ""),
                notes=str(form.get("notes") or ""),
            )
        except Exception as e:
            print("calc profile edit:", e)
        return RedirectResponse("/calc-profiles", 303)

    # GET /reports is owned by unified_hub_routes (4 subsections)

    @app.post("/reports/generate")
    async def reports_gen(
        request: Request, linac_id: str = Form(...),
        report_date: str = Form(...), notes: str = Form(""),
    ):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = create_report_from_date(
            linac_id, report_date,
            getattr(user, "full_name", None) or getattr(user, "username", ""),
            notes,
        )
        if not rep:
            raise HTTPException(400, "Could not create report")
        return RedirectResponse(f"/reports/{rep.id}/pdf", 303)

    @app.get("/reports/{rid}/pdf")
    async def report_pdf(request: Request, rid: str):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404, "Report not found")
        try:
            records = list_output_records(
                linac_id=rep.linac_id, report_date=rep.report_date,
            )
        except Exception:
            records = []
        pdf = build_report_pdf(rep, records)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{rid}.pdf"},
        )

    @app.post("/session/{sid}/energy/{bid}/save")
    async def session_energy_save(request: Request, sid: str, bid: str):
        user = _user(request)
        if not user:
            return _login()
        return RedirectResponse(f"/session/{sid}", 303)

    print("extra_routes OK (no GET /reports list)")
    return True
"
