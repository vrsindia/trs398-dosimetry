"""Brachytherapy Source QA — library tolerances, multi-trial, save only if satisfactory."""
from __future__ import annotations

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth import get_user_by_token
from app.calculations import brachy_source_qa as bsq
from app.brachy_qa_tolerances import ensure_brachy_tolerances, get_brachy_tol

COOKIE = "dosepro_session"
TEMPLATE = "brachy_source_qa.html"


def _floats(form, prefix: str, n_max: int = 20):
    vals = []
    for i in range(1, n_max + 1):
        raw = form.get("%s%d" % (prefix, i))
        if raw is None or str(raw).strip() == "":
            continue
        try:
            vals.append(float(raw))
        except Exception:
            pass
    return vals


def _save_session(user, annexure, title, rows, formula="", overall="", notes="", linac_id="", linac_name="Brachy source"):
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
    ensure_brachy_tolerances()

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _tpl(request: Request, **kwargs):
        ctx = dict(kwargs)
        ctx.setdefault("current_user", _user(request))
        ctx.setdefault("result", None)
        ctx.setdefault("section", "ton_toff")
        ctx.setdefault("error", "")
        ctx.setdefault("message", "")
        ctx.setdefault("saved_id", "")
        ctx.setdefault("chart", None)
        ctx.setdefault("can_save", False)
        ctx.setdefault("sources", bsq.list_sources())
        ctx.setdefault("tol_display", None)
        try:
            return templates.TemplateResponse(request=request, name=TEMPLATE, context=ctx)
        except TypeError:
            ctx["request"] = request
            return templates.TemplateResponse(TEMPLATE, ctx)

    @app.get("/brachy-source-qa", response_class=HTMLResponse)
    @app.get("/brachy/source-qa", response_class=HTMLResponse)
    async def brachy_qa_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        section = request.query_params.get("section") or "ton_toff"
        tol_map = {
            "timer_error": "brachy_timer_error",
            "linearity": "brachy_timer_linearity",
            "decay": "brachy_decay",
            "single": "brachy_tps_single",
            "multi": "brachy_tps_multi",
            "position": "brachy_position",
            "contamination": "brachy_contamination",
        }
        tol_display = get_brachy_tol(tol_map[section]) if section in tol_map else None
        return _tpl(request, current_user=user, section=section, tol_display=tol_display)

    @app.get("/brachy-source-qa/pdf/{sid}")
    async def brachy_qa_pdf(request: Request, sid: str):
        user = _user(request)
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
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=brachy_qa_%s.pdf" % sid, "Cache-Control": "no-store"},
            )
        except Exception as e:
            return Response("PDF error: %s" % e, status_code=500)

    # ---- Transit: multi-trial calculate then optional save ----
    @app.post("/brachy-source-qa/ton-toff", response_class=HTMLResponse)
    async def qa_ton_toff(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        secs = _floats(form, "secondary_")
        dwells = _floats(form, "dwell_")
        try:
            if len(secs) != len(dwells) or not secs:
                raise ValueError("Enter matching secondary and dwell times for each trial")
            multi = bsq.ton_toff_multi(secs, dwells)
            rows = [(f"Trial {i} TON/TOFF (s)", round(v, 4)) for i, v in enumerate(multi["trials"], 1)]
            rows.append(("Average TON/TOFF (s)", round(multi["average"], 4)))
            rows.append(("Number of trials", multi["n"]))
            formula = "TON/TOFF = (Secondary − Dwell) / 2"
            result = {"title": "Source transit time", "rows": rows, "formula": formula, "pass": True}
            # Transit has no % tolerance in library by default — treat as informational Satisfactory
            can_save = True
            saved_id = ""
            msg = ""
            if action == "save" and can_save:
                saved = _save_session(user, "source_transit", result["title"], rows, formula, overall="Satisfactory")
                saved_id = saved.get("id") or ""
                msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="ton_toff", result=result,
                can_save=can_save, saved_id=saved_id, message=msg,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="ton_toff", error=str(e))

    # ---- Timer error ----
    @app.post("/brachy-source-qa/timer-error", response_class=HTMLResponse)
    async def qa_timer_error(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        tol = get_brachy_tol("brachy_timer_error")
        try:
            r1s = _floats(form, "r1_")
            r2s = _floats(form, "r2_")
            if len(r1s) < 1 or len(r2s) < 1:
                raise ValueError("Enter at least one R1 and R2 trial")
            dwell_time = float(form.get("dwell_time") or 60)
            n_interruptions = int(float(form.get("n_interruptions") or 1))
            R1 = bsq.average(r1s)
            R2 = bsq.average(r2s)
            te = bsq.timer_error_sec(R1, R2, dwell_time, n_interruptions)
            pct = bsq.timer_error_percent(te, dwell_time)
            ok = bsq.within_tolerance(pct, tol["percent"])
            status = bsq.status_label(ok)
            rows = [
                ("R1 average (%d trials)" % len(r1s), round(R1, 6)),
                ("R2 average (%d trials)" % len(r2s), round(R2, 6)),
                ("Dwell time t (s)", dwell_time),
                ("Interruptions n", n_interruptions),
                ("Timer error (s)", round(te, 6)),
                ("Timer error (%)", round(pct, 6)),
                ("Tolerance (%) [library]", tol["percent"]),
                ("Status", status),
            ]
            formula = "Timer error = (R2−R1)·t / ((n+1)·R1 − R2)"
            result = {"title": "Timer error", "rows": rows, "formula": formula, "pass": ok}
            saved_id, msg = "", ""
            if action == "save":
                if not ok:
                    msg = "Cannot save — result is not satisfactory"
                else:
                    saved = _save_session(user, "timer_error", result["title"], rows, formula, overall=status)
                    saved_id = saved.get("id") or ""
                    msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="timer_error", result=result,
                can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="timer_error", error=str(e), tol_display=tol)

    # ---- Timer linearity + chart data ----
    @app.post("/brachy-source-qa/timer-linearity", response_class=HTMLResponse)
    async def qa_linearity(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        tol = get_brachy_tol("brachy_timer_linearity")
        try:
            times = _floats(form, "t_")
            charges = _floats(form, "c_")
            if len(times) != len(charges) or len(times) < 2:
                raise ValueError("Enter at least 2 matching time/charge pairs")
            fit = bsq.timer_linearity(times, charges)
            ok = bsq.within_tolerance(fit["max_residual_percent"], tol["percent"])
            status = bsq.status_label(ok)
            rows = [
                ("Number of points", len(times)),
                ("Slope (charge/s)", round(fit["slope"], 8)),
                ("Intercept", round(fit["intercept"], 8)),
                ("End error (s)", round(fit["end_error_s"], 6)),
                ("Max residual (%)", round(fit["max_residual_percent"], 6)),
                ("Tolerance (%) [library]", tol["percent"]),
                ("Status", status),
            ]
            for i, (t, ch, yh, rp) in enumerate(
                zip(fit["times"], fit["charges"], fit["fitted"], fit["residuals_percent"]), 1
            ):
                rows.append((f"Point {i}: t={t}, Q={ch}, fit={round(yh,6)}, resid%={round(rp,4)}", ""))
            formula = "Charge ≈ a·Time + b; end error ≈ b/a"
            result = {"title": "Timer linearity", "rows": rows, "formula": formula, "pass": ok}
            chart = {"times": fit["times"], "charges": fit["charges"], "fitted": fit["fitted"]}
            saved_id, msg = "", ""
            if action == "save":
                if not ok:
                    msg = "Cannot save — result is not satisfactory"
                else:
                    saved = _save_session(user, "timer_linearity", result["title"], rows, formula, overall=status)
                    saved_id = saved.get("id") or ""
                    msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="linearity", result=result,
                chart=chart, can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="linearity", error=str(e), tol_display=tol)

    # ---- Decay with source list ----
    @app.post("/brachy-source-qa/decay", response_class=HTMLResponse)
    async def qa_decay(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        tol = get_brachy_tol("brachy_decay")
        try:
            source = str(form.get("source_name") or "Ir-192")
            out = bsq.decay_check(
                str(form.get("calib_dt") or ""),
                str(form.get("qa_dt") or ""),
                float(form.get("tps_decay") or 0),
                source_name=source,
            )
            ok = bsq.within_tolerance(out["percent_deviation"], tol["percent"])
            status = bsq.status_label(ok)
            rows = [
                ("Source", out["source"]),
                ("Half-life (days)", round(out["half_life_days"], 4)),
                ("Day difference", round(out["day_difference"], 6)),
                ("Decay factor (manual)", round(out["decay_factor_manual"], 8)),
                ("Decay factor (TPS)", round(out["decay_factor_tps"], 8)),
                ("Deviation (%)", round(out["percent_deviation"], 6)),
                ("Tolerance (%) [library]", tol["percent"]),
                ("Status", status),
            ]
            formula = "DF = exp(−ln2 · Δt / T½) from source library"
            result = {"title": "Decay factor", "rows": rows, "formula": formula, "pass": ok}
            saved_id, msg = "", ""
            if action == "save":
                if not ok:
                    msg = "Cannot save — result is not satisfactory"
                else:
                    saved = _save_session(user, "decay", result["title"], rows, formula, overall=status)
                    saved_id = saved.get("id") or ""
                    msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="decay", result=result,
                can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="decay", error=str(e), tol_display=tol)

    @app.post("/brachy-source-qa/single-source", response_class=HTMLResponse)
    async def qa_single(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        tol = get_brachy_tol("brachy_tps_single")
        try:
            source = str(form.get("source_name") or "Ir-192")
            act = bsq.apparent_activity_at_qa(
                float(form.get("activity_mci_calib") or 0),
                str(form.get("calib_dt") or ""),
                str(form.get("qa_dt") or ""),
                source_name=source,
            )
            out = bsq.single_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=float(form.get("air_kerma_rate_const") or 4.082),
                dose_rate_constant=float(form.get("dose_rate_constant") or 1.1121),
                g_r=float(form.get("g_r") or 1),
                G_ratio=float(form.get("G_ratio") or 1),
                F=float(form.get("F") or 1),
                prescription_cgy=float(form.get("prescription_cgy") or 1000),
                tps_time_s=float(form.get("tps_time_s") or 0),
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tol["percent"])
            status = bsq.status_label(ok)
            rows = [
                ("Source", act["source"]),
                ("Half-life (days)", round(act["half_life_days"], 4)),
                ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                ("Manual time (s)", round(out["treatment_time_s"], 4)),
                ("TPS time (s)", float(form.get("tps_time_s") or 0)),
                ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                ("Tolerance (%) [library]", tol["percent"]),
                ("Status", status),
            ]
            formula = "Ḋ = SK·Λ·g·G·F; t = Dose/Ḋ"
            result = {"title": "Single source vs TPS", "rows": rows, "formula": formula, "pass": ok}
            saved_id, msg = "", ""
            if action == "save":
                if not ok:
                    msg = "Cannot save — result is not satisfactory"
                else:
                    saved = _save_session(user, "single_source", result["title"], rows, formula, overall=status)
                    saved_id = saved.get("id") or ""
                    msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="single", result=result,
                can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="single", error=str(e), tol_display=tol)

    @app.post("/brachy-source-qa/multi-source", response_class=HTMLResponse)
    async def qa_multi(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        action = str(form.get("action") or "calculate")
        tol = get_brachy_tol("brachy_tps_multi")
        try:
            source = str(form.get("source_name") or "Ir-192")
            act = bsq.apparent_activity_at_qa(
                float(form.get("activity_mci_calib") or 0),
                str(form.get("calib_dt") or ""),
                str(form.get("qa_dt") or ""),
                source_name=source,
            )
            out = bsq.multi_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=float(form.get("air_kerma_rate_const") or 4.082),
                dose_rate_constant=float(form.get("dose_rate_constant") or 1.1121),
                prescription_cgy=float(form.get("prescription_cgy") or 1000),
                tps_time_s=float(form.get("tps_time_s") or 0),
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tol["percent"])
            status = bsq.status_label(ok)
            rows = [
                ("Source", act["source"]),
                ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                ("Total dose-rate (cGy/h)", round(out["total_dose_rate_cgy_per_h"], 4)),
                ("Manual time (s)", round(out["treatment_time_s"], 4)),
                ("TPS time (s)", float(form.get("tps_time_s") or 0)),
                ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                ("Tolerance (%) [library]", tol["percent"]),
                ("Status", status),
            ]
            formula = "ΣḊi; t = Dose/ΣḊ"
            result = {"title": "Multi source vs TPS", "rows": rows, "formula": formula, "pass": ok}
            saved_id, msg = "", ""
            if action == "save":
                if not ok:
                    msg = "Cannot save — result is not satisfactory"
                else:
                    saved = _save_session(user, "multi_source", result["title"], rows, formula, overall=status)
                    saved_id = saved.get("id") or ""
                    msg = "Saved to history" if saved_id else "Save failed"
            return _tpl(
                request, current_user=user, section="multi", result=result,
                can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
            )
        except Exception as e:
            return _tpl(request, current_user=user, section="multi", error=str(e), tol_display=tol)

    @app.post("/brachy-source-qa/record", response_class=HTMLResponse)
    async def qa_record(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        section = str(form.get("section") or "contamination")
        action = str(form.get("action") or "save")
        title_map = {
            "contamination": "Contamination test",
            "position": "Positioning accuracy",
            "leakage": "Unit leakage",
            "survey": "Installation survey",
        }
        title = title_map.get(section, section)
        tol = None
        if section == "contamination":
            tol = get_brachy_tol("brachy_contamination")
        elif section == "position":
            tol = get_brachy_tol("brachy_position")
        rows = [
            ("Measured", str(form.get("measured") or "")),
            ("Background", str(form.get("background") or "")),
            ("Tolerance [library]", (str(tol["percent"]) + " " + (tol.get("notes") or "")) if tol else str(form.get("tolerance") or "")),
            ("Result", str(form.get("result_text") or form.get("notes") or "")),
        ]
        # Manual records: user declares satisfactory via checkbox
        ok = str(form.get("satisfactory") or "") in ("1", "on", "true", "yes")
        status = bsq.status_label(ok)
        rows.append(("Status", status))
        result = {"title": title, "rows": rows, "formula": "Manual record", "pass": ok}
        saved_id, msg = "", ""
        if action == "save":
            if not ok:
                msg = "Cannot save — mark as satisfactory only when within tolerance"
            else:
                saved = _save_session(user, section, title, rows, overall=status, notes=str(form.get("notes") or ""))
                saved_id = saved.get("id") or ""
                msg = "Saved to history" if saved_id else "Save failed"
        return _tpl(
            request, current_user=user, section=section, result=result,
            can_save=ok, saved_id=saved_id, message=msg, tol_display=tol,
        )

    print("brachy_qa_routes: library tol + multi-trial + save-if-PASS")
    return True
