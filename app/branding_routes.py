"""Department logo upload, linac list filter, MR corrections k_B."""

from __future__ import annotations
import base64
from typing import Optional

from fastapi import Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_CALCULATE, PERM_DEPT_EDIT, PERM_LIBRARY_VIEW
from app.models import (
    list_linacs, get_linac, list_detectors, update_department, get_department,
)
from app.session import get_session, SessionCorrectionFactors
from app.calculations.photon import calculate_k_TP, calculate_k_pol, calculate_k_s_two_voltage

COOKIE = "dosepro_session"
MAX_LOGO_BYTES = 512 * 1024


def register_branding_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    # Override /linac to exclude brachy machines
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/linac"
                 and "GET" in (getattr(r, "methods", set()) or set())]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/linac", response_class=HTMLResponse)
    async def linac_select(request: Request):
        user = _user(request)
        if not user or not user.has(PERM_CALCULATE):
            return _login()
        machines = []
        for l in list_linacs():
            cat = getattr(l, "category", "ct_linac") or "ct_linac"
            if cat != "brachy":
                machines.append(l)
        return templates.TemplateResponse(
            request=request, name="linac_select.html",
            context={"linacs": machines, "current_user": user},
        )

    # Override modality page context is already template-driven; block electron for MR
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/linac/{linac_id}/electron"
                 and "GET" in (getattr(r, "methods", set()) or set())]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/linac/{linac_id}/electron")
    async def start_electron_guard(request: Request, linac_id: str):
        user = _user(request)
        if not user or not user.has(PERM_CALCULATE):
            return _login()
        linac = get_linac(linac_id)
        if not linac:
            raise HTTPException(404)
        if getattr(linac, "category", "") == "mr_linac":
            return RedirectResponse(f"/linac/{linac_id}/photon", 303)
        if getattr(linac, "category", "") == "brachy":
            return RedirectResponse("/brachy", 303)
        from app.session import create_session
        sess = create_session(linac_id, "electron")
        return RedirectResponse(f"/session/{sess.id}/corrections", 303)

    # Corrections form + POST with k_B
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/session/{sid}/corrections"]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/session/{sid}/corrections", response_class=HTMLResponse)
    async def corr_form(request: Request, sid: str):
        user = _user(request)
        if not user or not user.has(PERM_CALCULATE):
            return _login()
        sess = get_session(sid)
        if not sess:
            raise HTTPException(404)
        linac = get_linac(sess.linac_id)
        is_mr = getattr(linac, "category", "") == "mr_linac" if linac else False
        return templates.TemplateResponse(
            request=request, name="session_corrections.html",
            context={
                "session": sess, "linac": linac, "modality": sess.modality,
                "detectors": list_detectors(), "current_user": user, "is_mr": is_mr,
            },
        )

    @app.post("/session/{sid}/corrections")
    async def corr_calc(
        request: Request, sid: str,
        temperature_C: float = Form(...),
        pressure_hPa: float = Form(...),
        M_plus: float = Form(...),
        M_minus: float = Form(...),
        M1: float = Form(...),
        M2: float = Form(...),
        V1: float = Form(...),
        V2: float = Form(...),
        detector_id: str = Form(""),
        k_B: float = Form(1.0),
    ):
        user = _user(request)
        if not user or not user.has(PERM_CALCULATE):
            return _login()
        sess = get_session(sid)
        if not sess:
            raise HTTPException(404)
        try:
            k_B_val = float(k_B)
        except Exception:
            k_B_val = 1.0
        sess.corrections = SessionCorrectionFactors(
            k_TP=calculate_k_TP(temperature_C, pressure_hPa),
            k_pol=calculate_k_pol(M_plus, M_minus),
            k_s=calculate_k_s_two_voltage(M1, M2, V1, V2),
            temperature_C=temperature_C,
            pressure_hPa=pressure_hPa,
            calculated=True,
        )
        # Store magnetic factor on session
        sess.k_B = k_B_val
        if detector_id:
            sess.detector_id = detector_id
        return RedirectResponse(f"/session/{sid}/energies", 303)

    @app.post("/department/logo")
    async def dept_logo(request: Request, logo: UploadFile = File(...)):
        user = _user(request)
        if not user or not user.has(PERM_DEPT_EDIT):
            return _login()
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
