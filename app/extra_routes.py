"""Extra routes: calc profiles, reports PDF, energy calculate/save."""

from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from typing import Optional
from datetime import datetime, date

from app.models import (
    list_calc_profiles, add_calc_profile, update_calc_profile, CalcProfile,
    get_default_calc_profile, list_linacs, get_linac, get_beam, get_detector, list_detectors,
    find_tolerance, check_tolerance, add_output_record, OutputRecord, list_output_records,
    list_reports, get_report, _new_id,
)
from app.session import get_session
from app.measurement_helpers import compute_output
from app.reports import create_report_from_date, build_report_pdf
from app.auth import (
    get_user_by_token, PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
    PERM_HISTORY_VIEW, PERM_TUNE,
)
from app.db import use_db
from app import repo

COOKIE = "dosepro_session"


def register_extra_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _require(request: Request, perm=None):
        user = _user(request)
        if not user:
            return None
        if perm and not user.has(perm):
            raise HTTPException(403)
        return user

    def _login():
        return RedirectResponse("/login", 303)

    try:
        from app.ux_routes import register_ux_routes
        register_ux_routes(app, templates)
    except Exception:
        pass
    try:
        from app.history_routes import register_history_routes
        register_history_routes(app, templates)
    except Exception:
        pass

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
    async def energy_calc_v2(
        request: Request, sid: str, bid: str,
        raw_charge_nC: float = Form(...),
        mu: float = Form(...),
        N_Dw: float = Form(0.04521),
        k_Q: float = Form(1.0),
        nominal_output: float = Form(1.0),
        append_reading: str = Form("0"),
        repeat_charge_nC: Optional[float] = Form(None),
    ):
        user = _require(request, PERM_CALCULATE)
        if not user:
            return _login()
        sess, beam = get_session(sid), get_beam(bid)
        if not sess or not beam:
            raise HTTPException(404)

        detector = get_detector(sess.detector_id) if getattr(sess, "detector_id", None) else None
        if detector:
            N_Dw = float(detector.calibration_factor)
        else:
            N_Dw = float(N_Dw) if N_Dw else 0.04521

        nominal = float(nominal_output) if nominal_output else float(
            getattr(beam, "nominal_output_cGy_MU", 1.0) or 1.0
        )
        k_Q = float(k_Q) if k_Q else float(beam.k_Q)

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
            computed = compute_output(readings, float(mu), N_Dw, k_Q, sess.corrections, profile)

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
                    "error": f"Calculation error: {e}",
                },
            )

    @app.get("/calc-profiles", response_class=HTMLResponse)
    async def calc_profiles_page(request: Request):
        user = _require(request, PERM_LIBRARY_VIEW)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="calc_profiles.html",
            context={"profiles": list_calc_profiles(), "current_user": user},
        )

    @app.post("/calc-profiles/add")
    async def calc_prof_add(
        request: Request, name: str = Form(...),
        use_k_TP: Optional[str] = Form(None), use_k_pol: Optional[str] = Form(None),
        use_k_s: Optional[str] = Form(None), use_k_Q: Optional[str] = Form(None),
        use_electrometer_factor: Optional[str] = Form(None),
    ):
        if not _require(request, PERM_LIBRARY_EDIT):
            return _login()
        add_calc_profile(CalcProfile(
            id=_new_id(), name=name,
            use_k_TP=bool(use_k_TP), use_k_pol=bool(use_k_pol), use_k_s=bool(use_k_s),
            use_k_Q=bool(use_k_Q), use_electrometer_factor=bool(use_electrometer_factor),
        ))
        return RedirectResponse("/calc-profiles", 303)

    @app.post("/calc-profiles/{pid}/edit")
    async def calc_prof_edit(
        request: Request, pid: str, name: str = Form(...),
        use_k_TP: Optional[str] = Form(None), use_k_pol: Optional[str] = Form(None),
        use_k_s: Optional[str] = Form(None), use_k_Q: Optional[str] = Form(None),
        use_electrometer_factor: Optional[str] = Form(None),
        is_default: Optional[str] = Form(None),
    ):
        if not _require(request, PERM_LIBRARY_EDIT):
            return _login()
        update_calc_profile(
            pid, name=name, use_k_TP=bool(use_k_TP), use_k_pol=bool(use_k_pol),
            use_k_s=bool(use_k_s), use_k_Q=bool(use_k_Q),
            use_electrometer_factor=bool(use_electrometer_factor), is_default=bool(is_default),
        )
        return RedirectResponse("/calc-profiles", 303)

    @app.get("/reports", response_class=HTMLResponse)
    async def reports_page(request: Request):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="reports.html",
            context={
                "reports": list_reports(), "linacs": list_linacs(),
                "today": date.today().isoformat(), "current_user": user,
            },
        )

    @app.post("/reports/generate")
    async def reports_gen(
        request: Request, linac_id: str = Form(...),
        report_date: str = Form(...), notes: str = Form(""),
    ):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = create_report_from_date(linac_id, report_date, user.full_name, notes)
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
            raise HTTPException(404)
        if use_db():
            records = repo.list_outputs(machine_id=rep.linac_id, report_date=rep.report_date)
        else:
            records = list_output_records(linac_id=rep.linac_id, report_date=rep.report_date)
        try:
            pdf_bytes = build_report_pdf(rep, records)
        except Exception as e:
            raise HTTPException(500, f"PDF generation failed: {e}")
        filename = f"dosepro_{rep.linac_name.replace(' ', '_')}_{rep.report_date}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/session/{sid}/energy/{bid}/save")
    async def energy_save(
        request: Request, sid: str, bid: str,
        measured_output: float = Form(...),
        nominal_output: float = Form(1.0),
        avg_charge: float = Form(0),
        readings_json: str = Form(""),
        mu: float = Form(100),
        tuned_output: Optional[float] = Form(None),
        physicist: str = Form(""),
        notes: str = Form(""),
    ):
        user = _require(request, PERM_CALCULATE)
        if not user:
            return _login()
        sess, beam = get_session(sid), get_beam(bid)
        if not sess or not beam:
            raise HTTPException(404)
        readings = []
        if readings_json:
            try:
                readings = [float(x) for x in readings_json.split(",") if x.strip()]
            except ValueError:
                readings = []
        can_tune = user.has(PERM_TUNE)
        tuning = can_tune and tuned_output is not None and tuned_output > 0
        final = tuned_output if tuning else measured_output
        nom = nominal_output or getattr(beam, "nominal_output_cGy_MU", 1.0)
        tol = find_tolerance(sess.modality, beam.nominal_energy, sess.linac_id, parameter="output")
        status = check_tolerance(final, nom, tol)
        tpr = None
        if hasattr(sess, "beam_quality_index"):
            tpr = sess.beam_quality_index.get(bid)
        rec = OutputRecord(
            id=_new_id(), linac_id=sess.linac_id, beam_id=bid, modality=sess.modality,
            energy=beam.nominal_energy, date_time=datetime.utcnow().isoformat(),
            measured_output_cGy_MU=measured_output,
            tuned_output_cGy_MU=tuned_output if tuning else None,
            tuning_performed=tuning, detector_id=getattr(sess, "detector_id", None),
            k_TP=sess.corrections.k_TP, k_pol=sess.corrections.k_pol, k_s=sess.corrections.k_s,
            k_Q=beam.k_Q, notes=notes, physicist=physicist or user.full_name,
            nominal_output_cGy_MU=nom, status=status,
            raw_readings=readings, average_reading_nC=avg_charge or None,
            tpr20_10=tpr, saved_for_report=True,
        )
        # Persist: Supabase if configured, else memory
        repo.save_output(rec)
        if beam.nominal_energy not in sess.completed_energies:
            sess.completed_energies.append(beam.nominal_energy)
        return RedirectResponse(f"/session/{sid}/energies", 303)

    return True
