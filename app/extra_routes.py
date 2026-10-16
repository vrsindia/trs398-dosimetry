"""Additional routes: calc profiles, reports, enhanced measurement save/repeat."""

from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from typing import Optional
from datetime import datetime, date
import json

from app.models import (
    list_calc_profiles, get_calc_profile, add_calc_profile, update_calc_profile, CalcProfile,
    get_default_calc_profile, list_linacs, get_linac, get_beam, get_detector,
    find_tolerance, check_tolerance, add_output_record, OutputRecord, list_output_records,
    list_reports, get_report, _new_id,
)
from app.session import get_session
from app.measurement_helpers import compute_output
from app.reports import build_report_html, create_report_from_date
from app.auth import (
    get_user_by_token, PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT, PERM_HISTORY_VIEW, PERM_TUNE,
)

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

    @app.get("/calc-profiles", response_class=HTMLResponse)
    async def calc_profiles_page(request: Request):
        user = _require(request, PERM_LIBRARY_VIEW)
        if not user:
            return _login()
        return templates.TemplateResponse(request=request, name="calc_profiles.html",
            context={"profiles": list_calc_profiles(), "current_user": user})

    @app.post("/calc-profiles/add")
    async def calc_prof_add(request: Request, name: str = Form(...),
                            use_k_TP: Optional[str] = Form(None), use_k_pol: Optional[str] = Form(None),
                            use_k_s: Optional[str] = Form(None), use_k_Q: Optional[str] = Form(None),
                            use_electrometer_factor: Optional[str] = Form(None)):
        if not _require(request, PERM_LIBRARY_EDIT):
            return _login()
        add_calc_profile(CalcProfile(
            id=_new_id(), name=name,
            use_k_TP=bool(use_k_TP), use_k_pol=bool(use_k_pol), use_k_s=bool(use_k_s),
            use_k_Q=bool(use_k_Q), use_electrometer_factor=bool(use_electrometer_factor),
        ))
        return RedirectResponse("/calc-profiles", 303)

    @app.post("/calc-profiles/{pid}/edit")
    async def calc_prof_edit(request: Request, pid: str, name: str = Form(...),
                             use_k_TP: Optional[str] = Form(None), use_k_pol: Optional[str] = Form(None),
                             use_k_s: Optional[str] = Form(None), use_k_Q: Optional[str] = Form(None),
                             use_electrometer_factor: Optional[str] = Form(None),
                             is_default: Optional[str] = Form(None)):
        if not _require(request, PERM_LIBRARY_EDIT):
            return _login()
        update_calc_profile(pid, name=name, use_k_TP=bool(use_k_TP), use_k_pol=bool(use_k_pol),
                            use_k_s=bool(use_k_s), use_k_Q=bool(use_k_Q),
                            use_electrometer_factor=bool(use_electrometer_factor),
                            is_default=bool(is_default))
        return RedirectResponse("/calc-profiles", 303)

    @app.get("/reports", response_class=HTMLResponse)
    async def reports_page(request: Request):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        return templates.TemplateResponse(request=request, name="reports.html",
            context={"reports": list_reports(), "linacs": list_linacs(),
                     "today": date.today().isoformat(), "current_user": user})

    @app.post("/reports/generate")
    async def reports_gen(request: Request, linac_id: str = Form(...), report_date: str = Form(...),
                          notes: str = Form("")):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = create_report_from_date(linac_id, report_date, user.full_name, notes)
        if not rep:
            raise HTTPException(400, "Could not create report")
        return RedirectResponse(f"/reports/{rep.id}", 303)

    @app.get("/reports/{rid}", response_class=HTMLResponse)
    async def report_view(request: Request, rid: str):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404)
        records = [r for r in list_output_records(linac_id=rep.linac_id) if r.id in rep.measurement_ids]
        if not records:
            records = list_output_records(linac_id=rep.linac_id, report_date=rep.report_date)
        return templates.TemplateResponse(request=request, name="report_view.html",
            context={"report": rep, "records": records, "current_user": user})

    @app.get("/reports/{rid}/html")
    async def report_html(request: Request, rid: str):
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404)
        records = list_output_records(linac_id=rep.linac_id, report_date=rep.report_date)
        html = build_report_html(rep, records)
        return Response(content=html, media_type="text/html",
                        headers={"Content-Disposition": f'inline; filename="dosepro_{rep.report_date}.html"'})

    @app.get("/reports/{rid}/doc")
    async def report_doc(request: Request, rid: str):
        """DOC-compatible: HTML Word can open, or plain document download."""
        user = _require(request, PERM_HISTORY_VIEW)
        if not user:
            return _login()
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404)
        records = list_output_records(linac_id=rep.linac_id, report_date=rep.report_date)
        html = build_report_html(rep, records)
        # Word opens .doc from HTML with MS header
        doc_html = (
            "<html xmlns:o='urn:schemas-microsoft-com:office:office' "
            "xmlns:w='urn:schemas-microsoft-com:office:word'>"
            "<head><meta charset='utf-8'></head><body>"
            + html.split("<body>", 1)[-1].replace("</body></html>", "")
            + "</body></html>"
        )
        return Response(
            content=doc_html.encode("utf-8"),
            media_type="application/msword",
            headers={"Content-Disposition": f'attachment; filename="dosepro_{rep.report_date}.doc"'},
        )

    @app.post("/session/{sid}/energy/{bid}/save")
    async def energy_save(request: Request, sid: str, bid: str,
                          measured_output: float = Form(...),
                          nominal_output: float = Form(1.0),
                          avg_charge: float = Form(0),
                          readings_json: str = Form(""),
                          mu: float = Form(100),
                          tuned_output: Optional[float] = Form(None),
                          physicist: str = Form(""), notes: str = Form("")):
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
        tol = find_tolerance(sess.modality, beam.nominal_energy, sess.linac_id, parameter="output")
        status = check_tolerance(final, nominal_output or beam.nominal_output_cGy_MU, tol)
        tpr = sess.beam_quality_index.get(bid) or beam.quality_index
        add_output_record(OutputRecord(
            id=_new_id(), linac_id=sess.linac_id, beam_id=bid, modality=sess.modality,
            energy=beam.nominal_energy, date_time=datetime.utcnow().isoformat(),
            measured_output_cGy_MU=measured_output,
            tuned_output_cGy_MU=tuned_output if tuning else None,
            tuning_performed=tuning, detector_id=sess.detector_id,
            k_TP=sess.corrections.k_TP, k_pol=sess.corrections.k_pol, k_s=sess.corrections.k_s,
            k_Q=beam.k_Q, notes=notes, physicist=physicist or user.full_name,
            nominal_output_cGy_MU=nominal_output or beam.nominal_output_cGy_MU,
            status=status, raw_readings=readings, average_reading_nC=avg_charge or None,
            tpr20_10=tpr, saved_for_report=True,
        ))
        if beam.nominal_energy not in sess.completed_energies:
            sess.completed_energies.append(beam.nominal_energy)
        return RedirectResponse(f"/session/{sid}/energies", 303)
