"""Self-contained activity + EBRT/brachy BED routes (no fragile imports)."""
from __future__ import annotations
import math
from typing import List, Optional
from fastapi import Request, Form
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


def _bed_n_d(n: float, d: float, ab: float) -> float:
    if n <= 0 or d < 0 or ab <= 0:
        return 0.0
    return n * d * (1.0 + d / ab)


def _eqd2_from_bed(bed: float, ab: float) -> float:
    if bed <= 0 or ab <= 0:
        return 0.0
    return bed / (1.0 + 2.0 / ab)


def _bed_doses(doses: List[float], ab: float, g: float = 1.0) -> float:
    total = 0.0
    for d in doses:
        if d and d > 0:
            total += float(d) * (1.0 + g * float(d) / ab)
    return total


def _decay(a0: float, half_life_days: float, elapsed_days: float) -> dict:
    if half_life_days <= 0:
        raise ValueError("Half-life must be positive")
    factor = math.exp(-math.log(2) * elapsed_days / half_life_days)
    return {
        "a0": a0,
        "half_life_days": half_life_days,
        "elapsed_days": elapsed_days,
        "activity": a0 * factor,
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
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    # ---- Activity ----
    @app.get("/activity", response_class=HTMLResponse)
    async def activity_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "current_user": user, "isotopes": ISOTOPES,
                "result": None, "error": None, "form": None,
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
        try:
            a0 = float(formdata.get("a0") or 0)
            unit = str(formdata.get("unit") or "Ci")
            isotope = str(formdata.get("isotope") or "").strip()
            hl = float(formdata.get("half_life_days") or 0)
            elapsed = float(formdata.get("elapsed_days") or 0)
            if isotope and isotope in ISOTOPES:
                hl = float(ISOTOPES[isotope]["half_life_days"])
            if a0 < 0 or elapsed < 0:
                raise ValueError("Activity and elapsed time must be ≥ 0")
            res = _decay(a0, hl, elapsed)
            result = {**res, "unit": unit, "isotope": isotope}
            form = {
                "a0": a0, "half_life_days": hl, "elapsed_days": elapsed,
                "unit": unit, "isotope": isotope,
            }
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            form = {
                "a0": formdata.get("a0"),
                "half_life_days": formdata.get("half_life_days"),
                "elapsed_days": formdata.get("elapsed_days"),
                "unit": formdata.get("unit") or "Ci",
                "isotope": formdata.get("isotope") or "",
            }
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "current_user": user, "isotopes": ISOTOPES,
                "result": result, "error": error, "form": form,
            },
        )

    # ---- EBRT + brachy ----
    @app.get("/bed-combined", response_class=HTMLResponse)
    async def combined_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={
                "current_user": user, "result": None, "error": None,
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
        try:
            # Collect all brachy_dose fields
            doses_raw = []
            if hasattr(form, "getlist"):
                doses_raw = list(form.getlist("brachy_dose"))
            if not doses_raw:
                for k, v in form.multi_items() if hasattr(form, "multi_items") else []:
                    if k == "brachy_dose":
                        doses_raw.append(v)
            if not doses_raw:
                one = form.get("brachy_dose")
                if one is not None:
                    doses_raw = [one]
            doses = []
            for x in doses_raw:
                s = str(x).strip()
                if s != "":
                    doses.append(float(s))
            ebrt_n = float(form.get("ebrt_n") or 0)
            ebrt_d = float(form.get("ebrt_d") or 0)
            ab = float(form.get("ab") or 10)
            g = float(form.get("g") or 1)
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
            inputs = {
                "ebrt_n": str(ebrt_n), "ebrt_d": str(ebrt_d),
                "ab": str(ab), "g": str(g),
                "brachy_doses": [str(d) for d in doses],
            }
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            inputs = {
                "ebrt_n": str(form.get("ebrt_n") or ""),
                "ebrt_d": str(form.get("ebrt_d") or ""),
                "ab": str(form.get("ab") or "10"),
                "g": str(form.get("g") or "1"),
                "brachy_doses": [str(x) for x in (form.getlist("brachy_dose") if hasattr(form, "getlist") else [])],
            }
            if not inputs["brachy_doses"]:
                inputs["brachy_doses"] = [""]
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={
                "current_user": user, "result": result,
                "error": error, "inputs": inputs,
            },
        )

    print("fix_calc: activity + bed-combined registered")
    return True
