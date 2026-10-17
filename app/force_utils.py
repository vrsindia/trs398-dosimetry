"""Utility routes: activity, bed/eqd2, ebrt+brachy (multi-fx), gap correction."""
from __future__ import annotations
from datetime import date

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"
UNITS = ["Ci", "mCi", "uCi", "Bq", "MBq", "GBq"]
_DONE = False


def register_force_utils(app, templates):
    global _DONE
    if _DONE:
        return True
    _DONE = True

    from app.auth import (
        get_user_by_token, PERM_CALCULATE,
        SEC_ACTIVITY, SEC_BED, SEC_BED_COMBINED, SEC_GAP,
    )
    from app.calculations.activity import calculate_activity, list_sources
    from app.calculations.bed import (
        calculate_bed_eqd2, calculate_ebrt_brachy_bed,
        calculate_gap_correction, ALPHA_BETA_PRESETS,
    )

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    def _need(request: Request, section: str = None):
        u = _user(request)
        if not u:
            return None
        if not u.has(PERM_CALCULATE) and section not in (SEC_BED, SEC_BED_COMBINED, SEC_GAP):
            # doctors may use bed tools without full calculate
            if section and u.has(section):
                return u
            raise HTTPException(403, "Insufficient permissions")
        if section and not u.has(section):
            # allow if they have calculate (legacy users without section keys)
            if not u.has(PERM_CALCULATE):
                raise HTTPException(403, "This section is not enabled for your account")
        return u

    @app.get("/utils-ping")
    async def force_ping():
        paths = sorted({
            getattr(r, "path", "") for r in app.router.routes
            if getattr(r, "path", "") in
            ("/activity", "/bed", "/bed-combined", "/gap", "/utils-ping")
        })
        return {"ok": True, "paths": paths, "version": "1.8.0"}

    # ---- Activity ----
    @app.get("/activity", response_class=HTMLResponse)
    async def force_activity_get(request: Request):
        user = _need(request, SEC_ACTIVITY)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "sources": list_sources(), "units": UNITS,
                "result": None, "error": None,
                "inputs": {
                    "source": "Ir-192", "activity": "10", "unit": "Ci",
                    "output_unit": "Ci", "mode": "days", "days": "30",
                    "reference_date": "", "calculation_date": date.today().isoformat(),
                },
                "today": date.today().isoformat(), "current_user": user,
            },
        )

    @app.post("/activity", response_class=HTMLResponse)
    async def force_activity_post(request: Request):
        user = _need(request, SEC_ACTIVITY)
        if not user:
            return _login()
        form = await request.form()
        source = str(form.get("source") or "Ir-192").strip()
        unit = str(form.get("unit") or "Ci").strip()
        output_unit = str(form.get("output_unit") or unit).strip()
        mode = str(form.get("mode") or "days").strip()
        activity_raw = str(form.get("activity") or "").strip()
        days_raw = str(form.get("days") or "").strip()
        reference_date = str(form.get("reference_date") or "").strip()
        calculation_date = str(form.get("calculation_date") or "").strip()
        inputs = {
            "source": source, "activity": activity_raw, "unit": unit,
            "output_unit": output_unit, "mode": mode, "days": days_raw,
            "reference_date": reference_date, "calculation_date": calculation_date,
        }
        error = result = None
        try:
            av = float(activity_raw)
            if mode == "dates":
                if not reference_date or not calculation_date:
                    raise ValueError("Both reference date and calculation date are required")
                result = calculate_activity(
                    source, av, unit,
                    reference_date=reference_date, calculation_date=calculation_date,
                    output_unit=output_unit,
                )
            else:
                if days_raw == "":
                    raise ValueError("Days since reference is required")
                result = calculate_activity(
                    source, av, unit, days=float(days_raw), output_unit=output_unit,
                )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "sources": list_sources(), "units": UNITS,
                "result": result, "error": error, "inputs": inputs,
                "today": date.today().isoformat(), "current_user": user,
            },
        )

    # ---- BED / EQD2 ----
    @app.get("/bed", response_class=HTMLResponse)
    async def force_bed_get(request: Request):
        user = _need(request, SEC_BED)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={
                "result": None, "error": None, "presets": ALPHA_BETA_PRESETS,
                "inputs": {
                    "total_dose": "50", "n_fractions": "25",
                    "alpha_beta": "10", "preset": "Early responding tissue (a/b=10)",
                },
                "current_user": user,
            },
        )

    @app.post("/bed", response_class=HTMLResponse)
    async def force_bed_post(request: Request):
        user = _need(request, SEC_BED)
        if not user:
            return _login()
        form = await request.form()
        total_dose = str(form.get("total_dose") or "").strip()
        n_fractions = str(form.get("n_fractions") or "").strip()
        alpha_beta = str(form.get("alpha_beta") or "").strip()
        preset = str(form.get("preset") or "").strip()
        inputs = {
            "total_dose": total_dose, "n_fractions": n_fractions,
            "alpha_beta": alpha_beta, "preset": preset,
        }
        error = result = None
        try:
            ab = float(alpha_beta)
            result = calculate_bed_eqd2(
                float(total_dose), float(n_fractions), ab, preset or f"a/b={ab}",
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={
                "result": result, "error": error, "presets": ALPHA_BETA_PRESETS,
                "inputs": inputs, "current_user": user,
            },
        )

    # ---- EBRT + Brachy (multi-fraction brachy) ----
    @app.get("/bed-combined", response_class=HTMLResponse)
    async def force_bed_c_get(request: Request):
        user = _need(request, SEC_BED_COMBINED)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={
                "result": None, "error": None,
                "inputs": {
                    "ebrt_total": "45", "ebrt_n": "25", "ebrt_ab": "10",
                    "brachy_ab": "10", "brachy_g": "1",
                    "brachy_doses": ["7"],
                },
                "current_user": user,
            },
        )

    @app.post("/bed-combined", response_class=HTMLResponse)
    async def force_bed_c_post(request: Request):
        user = _need(request, SEC_BED_COMBINED)
        if not user:
            return _login()
        form = await request.form()
        # Collect all brachy_dose fields (brachy_dose, brachy_dose_1, ... or list)
        doses = []
        for key in form.keys():
            if key == "brachy_dose" or key.startswith("brachy_dose_"):
                raw = str(form.get(key) or "").strip()
                if raw:
                    try:
                        doses.append(float(raw))
                    except ValueError:
                        pass
        # Also accept comma-separated brachy_doses
        multi = str(form.get("brachy_doses") or "").strip()
        if multi:
            for part in multi.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    try:
                        doses.append(float(part))
                    except ValueError:
                        pass

        inputs = {
            "ebrt_total": str(form.get("ebrt_total") or "").strip(),
            "ebrt_n": str(form.get("ebrt_n") or "").strip(),
            "ebrt_ab": str(form.get("ebrt_ab") or "").strip(),
            "brachy_ab": str(form.get("brachy_ab") or "").strip(),
            "brachy_g": str(form.get("brachy_g") or "1").strip(),
            "brachy_doses": [str(d) for d in doses] if doses else ["7"],
        }
        error = result = None
        try:
            if not doses:
                raise ValueError("Add at least one brachytherapy fraction dose")
            result = calculate_ebrt_brachy_bed(
                ebrt_total_dose=float(inputs["ebrt_total"]),
                ebrt_n=float(inputs["ebrt_n"]),
                ebrt_alpha_beta=float(inputs["ebrt_ab"]),
                brachy_doses=doses,
                brachy_alpha_beta=float(inputs["brachy_ab"]),
                brachy_g=float(inputs["brachy_g"] or 1),
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={"result": result, "error": error, "inputs": inputs, "current_user": user},
        )

    # ---- Gap correction ----
    @app.get("/gap", response_class=HTMLResponse)
    async def force_gap_get(request: Request):
        user = _need(request, SEC_GAP)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="gap.html",
            context={
                "result": None, "error": None,
                "inputs": {
                    "planned_total": "66", "planned_n": "33", "alpha_beta": "10",
                    "delivered_n": "20", "gap_days": "7", "k_gy_per_day": "0.6",
                },
                "current_user": user,
            },
        )

    @app.post("/gap", response_class=HTMLResponse)
    async def force_gap_post(request: Request):
        user = _need(request, SEC_GAP)
        if not user:
            return _login()
        form = await request.form()
        inputs = {
            "planned_total": str(form.get("planned_total") or "").strip(),
            "planned_n": str(form.get("planned_n") or "").strip(),
            "alpha_beta": str(form.get("alpha_beta") or "").strip(),
            "delivered_n": str(form.get("delivered_n") or "").strip(),
            "gap_days": str(form.get("gap_days") or "").strip(),
            "k_gy_per_day": str(form.get("k_gy_per_day") or "0.6").strip(),
        }
        error = result = None
        try:
            result = calculate_gap_correction(
                planned_total_dose=float(inputs["planned_total"]),
                planned_n=float(inputs["planned_n"]),
                alpha_beta=float(inputs["alpha_beta"]),
                delivered_n=float(inputs["delivered_n"]),
                gap_days=float(inputs["gap_days"]),
                k_gy_per_day=float(inputs["k_gy_per_day"] or 0.6),
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="gap.html",
            context={"result": result, "error": error, "inputs": inputs, "current_user": user},
        )

    print("force_utils: /activity /bed /bed-combined /gap /utils-ping registered")
    return True
