"""Brachytherapy Source QA worksheets — routes + form handlers."""
from __future__ import annotations

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token
from app.calculations import brachy_source_qa as bsq

COOKIE = "dosepro_session"
TEMPLATE = "brachy_source_qa.html"


def register_brachy_qa_routes(app, templates):
    # Keep existing /brachy if present; only own these paths
    for path in ("/brachy-source-qa", "/brachy/source-qa"):
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
        user = _user(request)
        if not user:
            return None
        role = (getattr(user, "role", "") or "").lower()
        if role in ("developer", "admin", "physicist", "technologist", "intern"):
            return user
        try:
            if user.has("sec_brachy") or user.has("calculate"):
                return user
        except Exception:
            pass
        return user  # soft: allow any logged-in user

    def _tpl(request: Request, **kwargs):
        ctx = dict(kwargs)
        ctx.setdefault("current_user", _user(request))
        ctx.setdefault("result", None)
        ctx.setdefault("section", "ton_toff")
        ctx.setdefault("error", "")
        ctx.setdefault("message", "")
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
        return _tpl(request, current_user=user, section=section)

    # ---- 2.5 / 2.6 TON/TOFF ----
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
            result = {
                "title": "TON / TOFF (source transit)",
                "rows": [
                    ("Secondary time (s)", secondary_time),
                    ("Dwell time (s)", dwell_time),
                    ("TON/TOFF (s)", round(val, 4)),
                ],
                "formula": "TON/TOFF = (Secondary Time − Dwell Time) / 2",
            }
            return _tpl(request, current_user=user, section="ton_toff", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="ton_toff", error=str(e))

    # ---- 4.3.1 Timer error ----
    @app.post("/brachy-source-qa/timer-error", response_class=HTMLResponse)
    async def qa_timer_error(
        request: Request,
        r1_t1: float = Form(...),
        r1_t2: float = Form(...),
        r1_t3: float = Form(...),
        r2_t1: float = Form(...),
        r2_t2: float = Form(...),
        r2_t3: float = Form(...),
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
            result = {
                "title": "Timer error (4.3.1)",
                "rows": [
                    ("R1 average (no interrupt)", round(R1, 6)),
                    ("R2 average (with interrupt)", round(R2, 6)),
                    ("Dwell time t (s)", dwell_time),
                    ("Interruptions n", n_interruptions),
                    ("Timer error (s)", round(te, 6)),
                    ("Timer error (%)", round(pct, 6)),
                    ("Tolerance (%)", tolerance_pct),
                    ("Status", bsq.status_label(ok)),
                ],
                "formula": "Timer error = (R2−R1)·t / ((n+1)·R1 − R2);  % = error·100/t",
                "pass": ok,
            }
            return _tpl(request, current_user=user, section="timer_error", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="timer_error", error=str(e))

    # ---- 4.3.2 Linearity ----
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
            result = {
                "title": "Timer linearity & end error (4.3.2)",
                "rows": [
                    ("Slope (charge/s)", round(fit["slope"], 8)),
                    ("Intercept", round(fit["intercept"], 8)),
                    ("End error estimate (s)", round(fit["end_error_s"], 6)),
                    ("Max residual (%)", round(fit["max_residual_percent"], 6)),
                    ("Tolerance (%)", tolerance_pct),
                    ("Status", bsq.status_label(ok)),
                ],
                "formula": "Charge ≈ a·Time + b; end error ≈ b/a",
                "pass": ok,
            }
            return _tpl(request, current_user=user, section="linearity", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="linearity", error=str(e))

    # ---- Decay check ----
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
            result = {
                "title": "Decay factor (manual vs TPS)",
                "rows": [
                    ("Day difference", round(out["day_difference"], 6)),
                    ("Decay factor (manual)", round(out["decay_factor_manual"], 8)),
                    ("Decay factor (TPS)", round(out["decay_factor_tps"], 8)),
                    ("Deviation (%)", round(out["percent_deviation"], 6)),
                    ("Tolerance (%)", tolerance_pct),
                    ("Status", bsq.status_label(ok)),
                ],
                "formula": "DF = exp(−ln2 · Δt / T½)",
                "pass": ok,
            }
            return _tpl(request, current_user=user, section="decay", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="decay", error=str(e))

    # ---- 5.2.5 Single source ----
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
            act = bsq.apparent_activity_at_qa(
                activity_mci_calib, calib_dt, qa_dt, half_life_days
            )
            out = bsq.single_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=air_kerma_rate_const,
                dose_rate_constant=dose_rate_constant,
                g_r=g_r,
                G_ratio=G_ratio,
                F=F,
                prescription_cgy=prescription_cgy,
                tps_time_s=tps_time_s,
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tolerance_pct)
            result = {
                "title": "Single-source TG-43 vs TPS (5.2.5)",
                "rows": [
                    ("Day difference", round(act["day_difference"], 6)),
                    ("Decay factor", round(act["decay_factor"], 8)),
                    ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                    ("Air-kerma strength", round(out["air_kerma_strength"], 4)),
                    ("Dose-rate (cGy/h)", round(out["dose_rate_cgy_per_h"], 4)),
                    ("Manual treatment time (s)", round(out["treatment_time_s"], 4)),
                    ("TPS treatment time (s)", tps_time_s),
                    ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                    ("Tolerance (%)", tolerance_pct),
                    ("Status", bsq.status_label(ok)),
                ],
                "formula": "Ḋ = SK·Λ·g(r)·G·F;  t = Dose / Ḋ",
                "pass": ok,
            }
            return _tpl(request, current_user=user, section="single", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="single", error=str(e))

    # ---- 5.2.6 Multi source ----
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
            act = bsq.apparent_activity_at_qa(
                activity_mci_calib, calib_dt, qa_dt, half_life_days
            )
            out = bsq.multi_source_treatment_time(
                activity_mci_at_qa=act["activity_mci"],
                air_kerma_rate_const=air_kerma_rate_const,
                dose_rate_constant=dose_rate_constant,
                prescription_cgy=prescription_cgy,
                tps_time_s=tps_time_s,
            )
            ok = bsq.within_tolerance(out.get("percent_deviation", 0), tolerance_pct)
            rows = [
                ("Day difference", round(act["day_difference"], 6)),
                ("Decay factor", round(act["decay_factor"], 8)),
                ("Activity at QA (mCi)", round(act["activity_mci"], 4)),
                ("Air-kerma strength", round(out["air_kerma_strength"], 4)),
            ]
            for i, c in enumerate(out["contributions"], 1):
                rows.append(
                    (f"Source {i} dose-rate (cGy/h)", round(c["dose_rate_cgy_per_h"], 4))
                )
            rows.extend([
                ("Total dose-rate (cGy/h)", round(out["total_dose_rate_cgy_per_h"], 4)),
                ("Manual treatment time (s)", round(out["treatment_time_s"], 4)),
                ("TPS treatment time (s)", tps_time_s),
                ("Deviation (%)", round(out.get("percent_deviation", 0), 6)),
                ("Tolerance (%)", tolerance_pct),
                ("Status", bsq.status_label(ok)),
            ])
            result = {
                "title": "Multi-source TG-43 vs TPS (5.2.6)",
                "rows": rows,
                "formula": "Sum Ḋi = SK·Λ·g·G·F at each dwell; t = Dose / ΣḊ",
                "pass": ok,
            }
            return _tpl(request, current_user=user, section="multi", result=result)
        except Exception as e:
            return _tpl(request, current_user=user, section="multi", error=str(e))

    # ---- 4.1 Contamination / 4.2 Position / 6.3 Leakage / 6.4 Survey (record) ----
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
        result = {
            "title": f"Recorded — {section}",
            "rows": [
                ("Measured", measured),
                ("Background", background),
                ("Tolerance", tolerance),
                ("Result / notes", result_text or notes),
            ],
            "formula": "Manual QA record (saved in session display)",
            "pass": None,
        }
        return _tpl(request, current_user=user, section=section, result=result, message="Recorded")

    print("brachy_qa_routes: /brachy-source-qa registered")
    return True
