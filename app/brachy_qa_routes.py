"""Brachytherapy Source QA — calculate, save history, PDF."""
from __future__ import annotations

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth import get_user_by_token
from app.calculations import brachy_source_qa as bsq

COOKIE = "dosepro_session"
TEMPLATE = "brachy_source_qa.html"


def _save_session(
    user,
    annexure: str,
    title: str,
    rows,
    formula: str = "",
    overall: str = "",
    notes: str = "",
    linac_id: str = "",
    linac_name: str = "Brachy source",
) -> dict:
    results = []
    for item in rows or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            results.append({"parameter": str(item[0]), "value": str(item[1])})
        elif isinstance(item, dict):
            results.append(item)
    try:
        from app.qa_results_store import save_qa_result
        row = save_qa_result(
            kind="brachy_source",
            linac_id=linac_id or "brachy",
            linac_name=linac_name or "Brachy source",
            overall=overall or "",
            results=results,
            performed_by=getattr(user, "username", "") or "",
            notes=(notes or "") + ((" | " + formula) if formula else ""),
        )
        row["annexure"] = annexure
        row["title"] = title
        row["formula"] = formula
        return row
    except Exception as e:
        print("brachy_qa save:", e)
        return {}


def register_brachy_qa_routes(app, templates):
    for path in (
        "/brachy-source-qa", "/brachy/source-qa",
        "/brachy-source-qa/pdf/{sid}",
    ):
        app.router.routes[:] = [
            r for r in list(app.router.routes)
            if getattr(r, "path", None) != path
        ]

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _require(request: Request):
        return _user(request)

    def _tpl(request: Request, **kwargs):
        ctx = dict(kwargs)
        ctx.setdefault("current_user", _user(request))
        ctx.setdefault("result", None)
        ctx.setdefault("section", "ton_toff")
        ctx.setdefault("error", "")
        ctx.setdefault("message", "")
        ctx.setdefault("saved_id", "")
        try:
            return templates.TemplateResponse(
                request=request, name=TEMPLATE, context=ctx,
            )
        except TypeError:
            ctx["request"] = request
            return templates.TemplateResponse(TEMPLATE, ctx)

    @app.get("/brachy-source-qa", response_class=HTMLResponse)
    @app.get("/brachy/source-qa", response_class=HTMLResponse)
    async def brachy_qa_page(request: Request):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        section = request.query_params.get("section") or "ton_toff"
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(request, current_user=user, section=section, message=msg)

    @app.get("/brachy-source-qa/pdf/{sid}")
    async def brachy_qa_pdf(request: Request, sid: str):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            from app.qa_results_store import get_qa_result, list_qa_results
            session = get_qa_result(sid)
            if not session:
                for r in list_qa_results(kind="brachy_source") or []:
                    if r.get("id") == sid:
                        session = r
                        break
            if not session:
                return Response("Session not found", status_code=404)
            from app.brachy_qa_pdf import build_brachy_source_qa_pdf
            pdf = build_brachy_source_qa_pdf(session)
            fname = "brachy_source_qa_%s.pdf" % sid
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=%s" % fname,
                    "Cache-Control": "no-store",
                },
            )
        except Exception as e:
            print("brachy_qa_pdf:", e)
            return Response("PDF error: %s" % e, status_code=500)

    def _done(request, user, section, result, saved):
        sid = saved.get("id") or ""
        msg = "Saved to history" if sid else ""
        return _tpl(
            request,
            current_user=user,
            section=section,
            result=result,
            saved_id=sid,
            message=msg,
        )

    @app.post("/brachy-source-qa/ton-toff", response_class=HTMLResponse)
    async def qa_ton_toff(
        request: Request,
        secondary_time: float = Form(...),
        dwell_time: float = Form(...),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            val = bsq.ton_toff(secondary_time, dwell_time)
            rows = [
                ("Secondary time (s)", secondary_time),
                ("Dwell time (s)", dwell_time),
                ("TON/TOFF (s)", round(val, 4)),
            ]
            formula = "TON/TOFF = (Secondary Time − Dwell Time) / 2"
            result = {"title": "Source transit time", "rows": rows, "formula": formula}
            saved = _save_session(user, "source_transit", result["title"], rows, formula)
            return _done(request, user, "ton_toff", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="ton_toff", error=str(e))

    @app.post("/brachy-source-qa/timer-error", response_class=HTMLResponse)
    async def qa_timer_error(
        request: Request,
        r1_t1: float = Form(...), r1_t2: float = Form(...), r1_t3: float = Form(...),
        r2_t1: float = Form(...), r2_t2: float = Form(...), r2_t3: float = Form(...),
        dwell_time: float = Form(60.0),
        n_interruptions: int = Form(1),
        tolerance_pct: float = Form(1.0),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            R1 = bsq.average([r1_t1, r1_t2, r1_t3])
            R2 = bsq.average([r2_t1, r2_t2, r2_t3])
            te = bsq.timer_error_sec(R1, R2, dwell_time, n_interruptions)
            pct = bsq.timer_error_percent(te, dwell_time)
            ok = bsq.within_tolerance(pct, tolerance_pct)
            status = bsq.status_label(ok)
            rows = [
                ("R1 average", round(R1, 6)),
                ("R2 average", round(R2, 6)),
                ("Dwell time t (s)", dwell_time),
                ("Interruptions n", n_interruptions),
                ("Timer error (s)", round(te, 6)),
                ("Timer error (%)", round(pct, 6)),
                ("Tolerance (%)", tolerance_pct),
                ("Status", status),
            ]
            formula = "Timer error = (R2−R1)·t / ((n+1)·R1 − R2); % = error·100/t"
            result = {"title": "Timer error", "rows": rows, "formula": formula, "pass": ok}
            saved = _save_session(user, "timer_error", result["title"], rows, formula, overall=status)
            return _done(request, user, "timer_error", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="timer_error", error=str(e))

    @app.post("/brachy-source-qa/timer-linearity", response_class=HTMLResponse)
    async def qa_linearity(
        request: Request,
        t1: float = Form(...), c1: float = Form(...),
        t2: float = Form(...), c2: float = Form(...),
        t3: float = Form(...), c3: float = Form(...),
        t4: float = Form(0.0), c4: float = Form(0.0),
        tolerance_pct: float = Form(1.0),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            times, charges = [t1, t2, t3], [c1, c2, c3]
            if t4 > 0 and c4 > 0:
                times.append(t4)
                charges.append(c4)
            fit = bsq.timer_linearity(times, charges)
            ok = bsq.within_tolerance(fit["max_residual_percent"], tolerance_pct)
            status = bsq.status_label(ok)
            rows = [
                ("Slope", round(fit["slope"], 8)),
                ("Intercept", round(fit["intercept"], 8)),
                ("End error (s)", round(fit["end_error_s"], 6)),
                ("Max residual (%)", round(fit["max_residual_percent"], 6)),
                ("Tolerance (%)", tolerance_pct),
                ("Status", status),
            ]
            formula = "Charge ≈ a·Time + b; end error ≈ b/a"
            result = {"title": "Timer linearity", "rows": rows, "formula": formula, "pass": ok}
            saved = _save_session(user, "timer_linearity", result["title"], rows, formula, overall=status)
            return _done(request, user, "linearity", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="linearity", error=str(e))

    @app.post("/brachy-source-qa/decay", response_class=HTMLResponse)
    async def qa_decay(
        request: Request,
        calib_dt: str = Form(...),
        qa_dt: str = Form(...),
        tps_decay: float = Form(...),
        half_life_days: float = Form(73.83),
        tolerance_pct: float = Form(1.0),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            out = bsq.decay_check(calib_dt, qa_dt, tps_decay, half_life_days)
            ok = bsq.within_tolerance(out["percent_deviation"], tolerance_pct)
            status = bsq.status_label(ok)
            rows = [
                ("Day difference", round(out["day_difference"], 6)),
                ("Decay factor (manual)", round(out["decay_factor_manual"], 8)),
                ("Decay factor (TPS)", round(out["decay_factor_tps"], 8)),
                ("Deviation (%)", round(out["percent_deviation"], 6)),
                ("Status", status),
            ]
            formula = "DF = exp(−ln2 · Δt / T½)"
            result = {"title": "Decay factor", "rows": rows, "formula": formula, "pass": ok}
            saved = _save_session(user, "decay", result["title"], rows, formula, overall=status)
            return _done(request, user, "decay", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="decay", error=str(e))

    @app.post("/brachy-source-qa/single-source", response_class=HTMLResponse)
    async def qa_single(
        request: Request,
        activity_mci_calib: float = Form(...),
        calib_dt: str = Form(...),
        qa_dt: str = Form(...),
        prescription_cgy: float = Form(1000.0),
        air_kerma_rate_const: float = Form(4.082),
        dose_rate_constant: float = Form(1.1121),
        g_r: float = Form(1.0),
        G_ratio: float = Form(1.0),
        F: float = Form(1.0),
        tps_time_s: float = Form(...),
        half_life_days: float = Form(73.83),
        tolerance_pct: float = Form(3.0),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            act = bsq.apparent_activity_at_qa(activity_mci_calib, calib_dt, qa_dt, half_life_days)
            out = bsq.single_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=air_kerma_rate_const,
                dose_rate_constant=dose_rate_constant,
                g_r=g_r, G_ratio=G_ratio, F=F,
                prescription_cgy=prescription_cgy,
                tps_time_s=tps_time_s,
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tolerance_pct)
            status = bsq.status_label(ok)
            rows = [
                ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                ("Decay factor", round(act["decay_factor"], 8)),
                ("Dose-rate (cGy/h)", round(out["dose_rate_cgy_per_h"], 4)),
                ("Manual time (s)", round(out["treatment_time_s"], 4)),
                ("TPS time (s)", tps_time_s),
                ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                ("Status", status),
            ]
            formula = "Ḋ = SK·Λ·g·G·F; t = Dose/Ḋ"
            result = {"title": "Single source vs TPS", "rows": rows, "formula": formula, "pass": ok}
            saved = _save_session(user, "single_source", result["title"], rows, formula, overall=status)
            return _done(request, user, "single", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="single", error=str(e))

    @app.post("/brachy-source-qa/multi-source", response_class=HTMLResponse)
    async def qa_multi(
        request: Request,
        activity_mci_calib: float = Form(...),
        calib_dt: str = Form(...),
        qa_dt: str = Form(...),
        prescription_cgy: float = Form(1000.0),
        air_kerma_rate_const: float = Form(4.082),
        dose_rate_constant: float = Form(1.1121),
        tps_time_s: float = Form(...),
        half_life_days: float = Form(73.83),
        tolerance_pct: float = Form(3.0),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            act = bsq.apparent_activity_at_qa(activity_mci_calib, calib_dt, qa_dt, half_life_days)
            out = bsq.multi_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=air_kerma_rate_const,
                dose_rate_constant=dose_rate_constant,
                prescription_cgy=prescription_cgy,
                tps_time_s=tps_time_s,
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tolerance_pct)
            status = bsq.status_label(ok)
            rows = [
                ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                ("Total dose-rate (cGy/h)", round(out["total_dose_rate_cgy_per_h"], 4)),
                ("Manual time (s)", round(out["treatment_time_s"], 4)),
                ("TPS time (s)", tps_time_s),
                ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                ("Status", status),
            ]
            formula = "ΣḊi; t = Dose/ΣḊ"
            result = {"title": "Multi source vs TPS", "rows": rows, "formula": formula, "pass": ok}
            saved = _save_session(user, "multi_source", result["title"], rows, formula, overall=status)
            return _done(request, user, "multi", result, saved)
        except Exception as e:
            return _tpl(request, current_user=user, section="multi", error=str(e))

    @app.post("/brachy-source-qa/record", response_class=HTMLResponse)
    async def qa_record(
        request: Request,
        section: str = Form("contamination"),
        notes: str = Form(""),
        measured: str = Form(""),
        background: str = Form(""),
        tolerance: str = Form(""),
        result_text: str = Form(""),
    ):
        user = _require(request)
        if not user:
            return RedirectResponse("/login", 303)
        title_map = {
            "contamination": "Contamination test",
            "position": "Positioning accuracy",
            "leakage": "Unit leakage",
            "survey": "Installation survey",
        }
        title = title_map.get(section, section)
        rows = [
            ("Measured", measured),
            ("Background", background),
            ("Tolerance", tolerance),
            ("Result", result_text or notes),
        ]
        result = {"title": title, "rows": rows, "formula": "Manual record"}
        saved = _save_session(user, section, title, rows, notes=notes or result_text)
        return _done(request, user, section, result, saved)

    print("brachy_qa_routes: calculate + save + PDF (plain names)")
    return True
