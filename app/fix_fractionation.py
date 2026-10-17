"""Fractionation pattern routes matching fractionation.html template."""
from __future__ import annotations
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "dosepro_session"


def register_fix_fractionation(app, templates):
    from app.auth import get_user_by_token

    # strip old
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) != "/fractionation"
    ]

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    @app.get("/fractionation", response_class=HTMLResponse)
    async def frac_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        return templates.TemplateResponse(
            request=request, name="fractionation.html",
            context={"current_user": user, "result": None, "error": None, "form": None},
        )

    @app.post("/fractionation", response_class=HTMLResponse)
    async def frac_calc(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        formdata = await request.form()

        def g(name, default=""):
            v = formdata.get(name)
            return str(v).strip() if v is not None else default

        ab_raw = g("ab", "10")
        preset = g("ab_preset")
        if preset == "early":
            ab_raw = "10"
        elif preset == "late":
            ab_raw = "3"
        elif preset == "prostate":
            ab_raw = "1.5"

        form = {
            "ref_n": g("ref_n"),
            "ref_d": g("ref_d"),
            "ab": ab_raw,
            "target_bed": g("target_bed"),
            "solve_n": g("solve_n"),
            "solve_d": g("solve_d"),
        }
        error = None
        result = None
        try:
            from app.calculations.bed import (
                bed_fractionated, eqd2_from_bed,
                fractionation_for_bed, alternative_patterns,
            )
            ab = float(ab_raw or 10)
            target = None
            if form["target_bed"]:
                target = float(form["target_bed"])
            elif form["ref_n"] and form["ref_d"]:
                target = bed_fractionated(float(form["ref_n"]), float(form["ref_d"]), ab)
            if target is None or target <= 0:
                raise ValueError("Enter a target BED or a reference schedule (n and d).")

            solved = None
            sn = float(form["solve_n"]) if form["solve_n"] else None
            sd = float(form["solve_d"]) if form["solve_d"] else None
            if sn is not None or sd is not None:
                solved = fractionation_for_bed(target, ab, n=sn, d=sd)

            table = alternative_patterns(target, ab)
            result = {
                "target_bed": target,
                "ab": ab,
                "solved": solved,
                "table": table,
            }
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        return templates.TemplateResponse(
            request=request, name="fractionation.html",
            context={
                "current_user": user, "result": result,
                "error": error, "form": form,
            },
        )

    return True
