"""Force-register logo + utility routes. Called from main and bootstrap."""
from __future__ import annotations
from datetime import date
from pathlib import Path

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse

COOKIE = "dosepro_session"
UNITS = ["Ci", "mCi", "uCi", "Bq", "MBq", "GBq"]
_DONE = False


def register_force_utils(app, templates):
    global _DONE
    if _DONE:
        return True
    _DONE = True

    from app.auth import get_user_by_token, PERM_CALCULATE

    try:
        from app.calculations.activity import calculate_activity, list_sources
        from app.calculations.bed import (
            calculate_bed_eqd2, calculate_ebrt_brachy_bed, ALPHA_BETA_PRESETS,
        )
    except Exception as e:
        print("force_utils import error:", e)
        raise

    static_dir = Path(__file__).resolve().parent / "static"

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    def _need(request: Request):
        u = _user(request)
        if not u:
            return None
        if not u.has(PERM_CALCULATE):
            raise HTTPException(403, "Insufficient permissions")
        return u

    @app.get("/logo.jpg")
    async def force_logo():
        p = static_dir / "garuda.jpg"
        if p.exists():
            return FileResponse(str(p), media_type="image/jpeg",
                                headers={"Cache-Control": "public, max-age=86400"})
        s = static_dir / "garuda.svg"
        if s.exists():
            return FileResponse(str(s), media_type="image/svg+xml")
        return JSONResponse({"error": "logo file missing", "looked": str(p)}, status_code=404)

    @app.get("/utils-ping")
    async def force_ping():
        paths = sorted({getattr(r, "path", "") for r in app.router.routes
                        if getattr(r, "path", "") in
                        ("/activity", "/bed", "/bed-combined", "/utils-ping", "/logo.jpg")})
        return {"ok": True, "paths": paths, "logo": (static_dir / "garuda.jpg").exists()}

    @app.get("/activity", response_class=HTMLResponse)
    async def force_activity_get(request: Request):
        user = _need(request)
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
        user = _need(request)
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
                result = calculate_activity(source, av, unit, days=float(days_raw), output_unit=output_unit)
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

    @app.get("/bed", response_class=HTMLResponse)
    async def force_bed_get(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={
                "result": None, "error": None, "presets": ALPHA_BETA_PRESETS,
                "inputs": {
                    "total_dose": "50", "n_fractions": "25",
                    "alpha_beta": "10", "preset": "Tumour (early, a/b=10)",
                },
                "current_user": user,
            },
        )

    @app.post("/bed", response_class=HTMLResponse)
    async def force_bed_post(request: Request):
        user = _need(request)
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
            result = calculate_bed_eqd2(float(total_dose), float(n_fractions), ab, preset or f"a/b={ab}")
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={
                "result": result, "error": error, "presets": ALPHA_BETA_PRESETS,
                "inputs": inputs, "current_user": user,
            },
        )

    @app.get("/bed-combined", response_class=HTMLResponse)
    async def force_bed_c_get(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={
                "result": None, "error": None,
                "inputs": {
                    "ebrt_total": "45", "ebrt_n": "25", "ebrt_ab": "10",
                    "brachy_dose": "7", "brachy_ab": "10", "brachy_g": "1",
                    "use_oar": "0", "ebrt_ab_oar": "3", "brachy_ab_oar": "3",
                },
                "current_user": user,
            },
        )

    @app.post("/bed-combined", response_class=HTMLResponse)
    async def force_bed_c_post(request: Request):
        user = _need(request)
        if not user:
            return _login()
        form = await request.form()
        inputs = {
            "ebrt_total": str(form.get("ebrt_total") or "").strip(),
            "ebrt_n": str(form.get("ebrt_n") or "").strip(),
            "ebrt_ab": str(form.get("ebrt_ab") or "").strip(),
            "brachy_dose": str(form.get("brachy_dose") or "").strip(),
            "brachy_ab": str(form.get("brachy_ab") or "").strip(),
            "brachy_g": str(form.get("brachy_g") or "1").strip(),
            "use_oar": str(form.get("use_oar") or "0").strip(),
            "ebrt_ab_oar": str(form.get("ebrt_ab_oar") or "3").strip(),
            "brachy_ab_oar": str(form.get("brachy_ab_oar") or "3").strip(),
        }
        error = result = None
        try:
            kwargs = dict(
                ebrt_total_dose=float(inputs["ebrt_total"]),
                ebrt_n=float(inputs["ebrt_n"]),
                ebrt_alpha_beta=float(inputs["ebrt_ab"]),
                brachy_dose=float(inputs["brachy_dose"]),
                brachy_alpha_beta=float(inputs["brachy_ab"]),
                brachy_g=float(inputs["brachy_g"] or 1),
            )
            if inputs["use_oar"] == "1":
                kwargs["ebrt_alpha_beta_oar"] = float(inputs["ebrt_ab_oar"])
                kwargs["brachy_alpha_beta_oar"] = float(inputs["brachy_ab_oar"])
            result = calculate_ebrt_brachy_bed(**kwargs)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={"result": result, "error": error, "inputs": inputs, "current_user": user},
        )

    print("force_utils: registered /activity /bed /bed-combined /logo.jpg /utils-ping")
    return True
