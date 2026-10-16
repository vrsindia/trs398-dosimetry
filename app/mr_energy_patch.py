"""Ensure energy calculation multiplies by session.k_B (MR magnetic factor)."""

from __future__ import annotations
from typing import Optional
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_CALCULATE
from app.models import get_beam, get_detector, get_linac, find_tolerance, check_tolerance, get_default_calc_profile
from app.session import get_session
from app.measurement_helpers import compute_output

COOKIE = "dosepro_session"


def register_mr_energy_patch(app, templates):
    to_remove = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", set()) or set()
        if path == "/session/{sid}/energy/{bid}" and "POST" in methods:
            to_remove.append(r)
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.post("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
    async def energy_calc_kb(
        request: Request, sid: str, bid: str,
        raw_charge_nC: float = Form(...),
        mu: float = Form(...),
        N_Dw: float = Form(0.04521),
        k_Q: float = Form(1.0),
        nominal_output: float = Form(1.0),
        append_reading: str = Form("0"),
        repeat_charge_nC: Optional[float] = Form(None),
    ):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_CALCULATE):
            return RedirectResponse("/login", 303)
        sess, beam = get_session(sid), get_beam(bid)
        if not sess or not beam:
            raise HTTPException(404)
        detector = get_detector(sess.detector_id) if getattr(sess, "detector_id", None) else None
        if detector:
            N_Dw = float(detector.calibration_factor)
        else:
            try:
                N_Dw = float(N_Dw)
            except Exception:
                N_Dw = 0.04521
        nominal = float(nominal_output) if nominal_output else float(
            getattr(beam, "nominal_output_cGy_MU", 1.0) or 1.0
        )
        k_Q = float(k_Q) if k_Q else float(beam.k_Q)
        k_B = float(getattr(sess, "k_B", 1.0) or 1.0)

        if not hasattr(sess, "beam_readings") or sess.beam_readings is None:
            sess.beam_readings = {}
        if bid not in sess.beam_readings:
            sess.beam_readings[bid] = []

        try:
            if append_reading == "1" and repeat_charge_nC is not None:
                sess.beam_readings[bid].append(float(repeat_charge_nC))
            else:
                sess.beam_readings[bid] = [float(raw_charge_nC)]
            readings = list(sess.beam_readings[bid])
            profile = get_default_calc_profile()
            computed = compute_output(
                readings, float(mu), N_Dw, k_Q, sess.corrections, profile, k_B=k_B,
            )

            class ER:
                pass
            result = ER()
            for k, v in computed.items():
                setattr(result, k, v)

            tol = find_tolerance(sess.modality, beam.nominal_energy, sess.linac_id, parameter="output")
            status = check_tolerance(computed["output_cGy_MU"], nominal, tol)
            beam_qi = None
            if hasattr(sess, "beam_quality_index") and sess.beam_quality_index:
                beam_qi = sess.beam_quality_index.get(bid)
            if beam_qi is None:
                beam_qi = getattr(beam, "quality_index", None)

            return templates.TemplateResponse(
                request=request, name="session_energy_calc.html",
                context={
                    "session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                    "detector": detector, "beam_qi": beam_qi, "profile": profile,
                    "result": result, "status": status, "tolerance": tol,
                    "nominal_output": nominal, "current_user": user,
                    "prior_readings": readings[:-1] if len(readings) > 1 else [],
                    "last_reading": readings[-1], "last_mu": mu, "error": None,
                    "k_B": k_B,
                },
            )
        except Exception as e:
            return templates.TemplateResponse(
                request=request, name="session_energy_calc.html",
                context={
                    "session": sess, "beam": beam, "linac": get_linac(sess.linac_id),
                    "detector": detector, "beam_qi": getattr(beam, "quality_index", None),
                    "profile": get_default_calc_profile(),
                    "result": None, "status": None, "tolerance": None,
                    "nominal_output": nominal, "current_user": user,
                    "prior_readings": [], "last_reading": raw_charge_nC, "last_mu": mu,
                    "error": f"Calculation error: {e}", "k_B": k_B,
                },
            )
