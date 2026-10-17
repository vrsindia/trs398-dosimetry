"""Self-contained activity + EBRT/brachy BED routes."""
from __future__ import annotations
import math
from typing import List
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "dosepro_session"

ISOTOPES = {
    "Ir-192": {"half_life_days": 73.83, "use": "HDR brachytherapy"},
    "Co-60": {"half_life_days": 1925.2, "use": "Teletherapy / HDR"},
    "Cs-137": {"half_life_days": 11019.0, "use": "LDR / calibration"},
    "I-125": {"half_life_days": 59.4, "use": "LDR seeds"},
    "Pd-103": {"half_life_days": 16.99, "use": "LDR seeds"},
    "Au-198": {"half_life_days": 2.70, "use": "LDR seeds"},
    "I-131": {"half_life_days": 8.02, "use": "Thyroid"},
    "Sr-90": {"half_life_days": 10512.0, "use": "Ophthalmic / beta"},
    "Y-90": {"half_life_days": 2.67, "use": "Radioembolisation"},
    "Tc-99m": {"half_life_days": 0.2504, "use": "Diagnostic"},
    "F-18": {"half_life_days": 0.076, "use": "PET"},
}


def _bed_n_d(n, d, ab):
    if n <= 0 or d < 0 or ab <= 0:
        return 0.0
    return n * d * (1.0 + d / ab)


def _eqd2_from_bed(bed, ab):
    if bed <= 0 or ab <= 0:
        return 0.0
    return bed / (1.0 + 2.0 / ab)


def _bed_doses(doses, ab, g=1.0):
    total = 0.0
    for d in doses:
        if d and d > 0:
            total += float(d) * (1.0 + g * float(d) / ab)
    return total


def _decay(a0, half_life_days, elapsed_days):
    if half_life_days <= 0:
        raise ValueError("Half-life must be positive")
    factor = math.exp(-math.log(2) * elapsed_days / half_life_days)
    return {
        "a0": float(a0),
        "half_life_days": float(half_life_days),
        "elapsed_days": float(elapsed_days),
        "activity": float(a0) * factor,
        "decay_factor": factor,
    }


def register_fix_calc(app, templates):
    from app.auth import get_user_by_token

    paths = {"/activity", "/bed-combined"}
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in paths
    ]

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _login():
        return RedirectResponse("/login", 303)

    @app.get("/activity", response_class=HTMLResponse)
    async def activity_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            "activity.html",
            {
                "request": request,
                "current_user": user,
                "isotopes": ISOTOPES,
                "result": None,
                "error": None,
                "form": {
                    "a0": "10",
                    "half_life_days": "73.83",
                    "elapsed_days": "7",
                    "unit": "Ci",
                    "isotope": "Ir-192",
                },
            },
        )

    @app.post("/activity", response_class=HTMLResponse)
    async def activity_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        formdata = await request.form()
        error = None
        result = None
        isotope = str(formdata.get("isotope") or "").strip()
        unit = str(formdata.get("unit") or "Ci")
        form = {
            "a0": str(formdata.get("a0") or ""),
            "half_life_days": str(formdata.get("half_life_days") or ""),
            "elapsed_days": str(formdata.get("elapsed_days") or ""),
            "unit": unit,
            "isotope": isotope,
        }
        try:
            a0 = float(form["a0"] or 0)
            elapsed = float(form["elapsed_days"] or 0)
            hl = float(form["half_life_days"] or 0)
            if isotope and isotope in ISOTOPES:
                hl = float(ISOTOPES[isotope]["half_life_days"])
                form["half_life_days"] = str(hl)
            if a0 < 0 or elapsed < 0:
                raise ValueError("Activity and elapsed time must be ≥ 0")
            if hl <= 0:
                raise ValueError("Half-life must be positive (select an isotope or enter a custom value)")
            res = _decay(a0, hl, elapsed)
            result = {
                "a0": res["a0"],
                "half_life_days": res["half_life_days"],
                "elapsed_days": res["elapsed_days"],
                "activity": res["activity"],
                "decay_factor": res["decay_factor"],
                "unit": unit,
                "isotope": isotope,
            }
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            "activity.html",
            {
                "request": request,
                "current_user": user,
                "isotopes": ISOTOPES,
                "result": result,
                "error": error,
                "form": form,
            },
        )

    @app.get("/bed-combined", response_class=HTMLResponse)
    async def combined_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            "bed_combined.html",
            {
                "request": request,
                "current_user": user,
                "result": None,
                "error": None,
                "inputs": {
                    "ebrt_n": "25", "ebrt_d": "1.8", "ab": "10",
                    "brachy_doses": ["7", "7"], "g": "1",
                },
            },
        )

    @app.post("/bed-combined", response_class=HTMLResponse)
    async def combined_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        error = None
        result = None
        doses_raw = list(form.getlist("brachy_dose")) if hasattr(form, "getlist") else []
        if not doses_raw:
            one = form.get("brachy_dose")
            doses_raw = [one] if one is not None else []
        doses = []
        for x in doses_raw:
            s = str(x).strip()
            if s:
                try:
                    doses.append(float(s))
                except ValueError:
                    pass
        inputs = {
            "ebrt_n": str(form.get("ebrt_n") or ""),
            "ebrt_d": str(form.get("ebrt_d") or ""),
            "ab": str(form.get("ab") or "10"),
            "g": str(form.get("g") or "1"),
            "brachy_doses": [str(d) for d in doses] or [""],
        }
        try:
            ebrt_n = float(inputs["ebrt_n"] or 0)
            ebrt_d = float(inputs["ebrt_d"] or 0)
            ab = float(inputs["ab"] or 10)
            g = float(inputs["g"] or 1)
            if ebrt_n <= 0 or ebrt_d < 0:
                raise ValueError("EBRT fractions and dose/fx must be positive")
            if ab <= 0:
                raise ValueError("α/β must be positive")
            if not doses:
                raise ValueError("Enter at least one brachytherapy fraction dose")
            ebrt_bed = _bed_n_d(ebrt_n, ebrt_d, ab)
            ebrt_eqd2 = _eqd2_from_bed(ebrt_bed, ab)
            brachy_bed = _bed_doses(doses, ab, g)
            brachy_eqd2 = _eqd2_from_bed(brachy_bed, ab)
            total_bed = ebrt_bed + brachy_bed
            total_eqd2 = _eqd2_from_bed(total_bed, ab)
            result = {
                "ab": ab, "g": g,
                "ebrt_n": ebrt_n, "ebrt_d": ebrt_d,
                "ebrt_total": ebrt_n * ebrt_d,
                "ebrt_bed": ebrt_bed, "ebrt_eqd2": ebrt_eqd2,
                "brachy_doses": doses,
                "brachy_bed": brachy_bed, "brachy_eqd2": brachy_eqd2,
                "total_bed": total_bed, "total_eqd2": total_eqd2,
            }
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            "bed_combined.html",
            {
                "request": request,
                "current_user": user,
                "result": result,
                "error": error,
                "inputs": inputs,
            },
        )

    print("fix_calc: activity + bed-combined registered")
    return True
