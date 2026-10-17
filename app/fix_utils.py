"""Force-register working utility routes (strip broken ones first).
Call last from bootstrap so these always win.
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"


def _strip(app, paths):
    paths = set(paths)
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in paths
    ]


def register_fix_utils(app, templates):
    from app.auth import get_user_by_token

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _need(request: Request) -> Optional[object]:
        user = _user(request)
        if not user:
            return None
        # developer/admin always; others need calculate or active account
        role = (getattr(user, "role", "") or "").lower()
        if role in ("developer", "admin"):
            return user
        if hasattr(user, "has") and (user.has("calculate") or user.active):
            return user
        return user  # logged-in users can use utilities

    def _login():
        return RedirectResponse("/login", 303)

    paths = [
        "/output", "/activity", "/bed", "/bed-combined",
        "/gap", "/fractionation", "/eqsquare", "/mu", "/units",
        "/nt-constraints", "/nt-constraints/add", "/nt-constraints/edit",
        "/nt-constraints/delete", "/utils-ping",
    ]
    _strip(app, paths)

    # ---- Linac alias (home used to link /output) ----
    @app.get("/output")
    async def output_alias():
        return RedirectResponse("/linac", 303)

    @app.get("/utils-ping")
    async def utils_ping():
        found = sorted({
            getattr(r, "path", "") for r in app.router.routes
            if getattr(r, "path", "") in paths
        })
        return JSONResponse({"ok": True, "paths": found, "module": "fix_utils"})

    # ==================================================================
    # Source activity
    # ==================================================================
    @app.get("/activity", response_class=HTMLResponse)
    async def activity_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import ISOTOPES
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "current_user": user, "result": None, "error": None,
                "form": None, "isotopes": ISOTOPES,
            },
        )

    @app.post("/activity", response_class=HTMLResponse)
    async def activity_calc(
        request: Request,
        a0: float = Form(...),
        half_life_days: float = Form(...),
        elapsed_days: float = Form(...),
        unit: str = Form("Ci"),
        isotope: str = Form(""),
    ):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import ISOTOPES, decay_activity
        error = None
        result = None
        form = {
            "a0": a0, "half_life_days": half_life_days,
            "elapsed_days": elapsed_days, "unit": unit, "isotope": isotope,
        }
        try:
            hl = half_life_days
            if isotope and isotope in ISOTOPES:
                hl = float(ISOTOPES[isotope]["half_life_days"])
                form["half_life_days"] = hl
            res = decay_activity(a0, hl, elapsed_days)
            result = {**res, "unit": unit, "isotope": isotope}
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="activity.html",
            context={
                "current_user": user, "result": result, "error": error,
                "form": form, "isotopes": ISOTOPES,
            },
        )

    # ==================================================================
    # BED / EQD2 (simple)
    # ==================================================================
    @app.get("/bed", response_class=HTMLResponse)
    async def bed_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={"current_user": user, "result": None, "error": None},
        )

    @app.post("/bed", response_class=HTMLResponse)
    async def bed_calc(
        request: Request,
        n: float = Form(...),
        d: float = Form(...),
        ab: float = Form(...),
    ):
        user = _need(request)
        if not user:
            return _login()
        error = None
        result = None
        try:
            from app.calculations.bed import bed_fractionated, eqd2_fractionated
            bed = bed_fractionated(n, d, ab)
            eqd2 = eqd2_fractionated(n, d, ab)
            result = {
                "n": n, "d": d, "ab": ab,
                "bed": bed, "eqd2": eqd2,
                "total_dose": n * d,
            }
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="bed.html",
            context={"current_user": user, "result": result, "error": error},
        )

    # ==================================================================
    # EBRT + multi-fraction brachy BED
    # ==================================================================
    @app.get("/bed-combined", response_class=HTMLResponse)
    async def bed_combined_page(request: Request):
        user = _need(request)
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
    async def bed_combined_calc(request: Request):
        user = _need(request)
        if not user:
            return _login()
        form = await request.form()
        error = None
        result = None
        brachy_raw = form.getlist("brachy_dose") if hasattr(form, "getlist") else []
        if not brachy_raw:
            # single field fallback
            one = form.get("brachy_dose")
            brachy_raw = [one] if one else []
        inputs = {
            "ebrt_n": str(form.get("ebrt_n") or ""),
            "ebrt_d": str(form.get("ebrt_d") or ""),
            "ab": str(form.get("ab") or "10"),
            "g": str(form.get("g") or "1"),
            "brachy_doses": [str(x) for x in brachy_raw if str(x).strip() != ""],
        }
        try:
            from app.calculations.bed import calculate_ebrt_brachy_bed
            doses = [float(x) for x in inputs["brachy_doses"]]
            res = calculate_ebrt_brachy_bed(
                ebrt_n=float(inputs["ebrt_n"]),
                ebrt_d=float(inputs["ebrt_d"]),
                brachy_doses=doses,
                ab=float(inputs["ab"]),
                g=float(inputs["g"] or 1),
            )
            # flatten dataclass / object to dict for template
            result = {
                "ab": res.ab,
                "ebrt_n": res.ebrt_n,
                "ebrt_d": res.ebrt_d,
                "ebrt_total": res.ebrt_n * res.ebrt_d,
                "ebrt_bed": res.ebrt_bed,
                "ebrt_eqd2": res.ebrt_eqd2,
                "brachy_doses": list(res.brachy_doses),
                "brachy_bed": res.brachy_bed,
                "brachy_eqd2": res.brachy_eqd2,
                "total_bed": res.total_bed,
                "total_eqd2": res.total_eqd2,
                "g": res.g_factor,
                "brachy_fractions": [
                    {
                        "dose": d,
                        "bed": d * (1 + d / (res.ab / max(res.g_factor, 1e-9))),
                        "eqd2": (d * (1 + d / res.ab)) / (1 + 2.0 / res.ab),
                    }
                    for d in res.brachy_doses
                ],
            }
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="bed_combined.html",
            context={
                "current_user": user, "result": result, "error": error,
                "inputs": inputs,
            },
        )

    # ==================================================================
    # Gap correction
    # ==================================================================
    @app.get("/gap", response_class=HTMLResponse)
    async def gap_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="gap.html",
            context={"current_user": user, "result": None, "error": None},
        )

    @app.post("/gap", response_class=HTMLResponse)
    async def gap_calc(request: Request):
        user = _need(request)
        if not user:
            return _login()
        form = await request.form()

        def _f(name, default=None):
            v = form.get(name)
            if v is None or str(v).strip() == "":
                return default
            return v

        error = None
        result = None
        try:
            from app.calculations.bed import calculate_gap_correction
            td = _f("total_days")
            cn = _f("custom_remaining_n")
            cd = _f("custom_remaining_d")
            result = calculate_gap_correction(
                planned_n=float(_f("planned_n", 30)),
                planned_d=float(_f("planned_d", 2)),
                delivered_n=float(_f("delivered_n", 0)),
                gap_days=float(_f("gap_days", 0) or 0),
                ab=float(_f("ab", 10)),
                start_date=_f("start_date") or None,
                gap_start_date=_f("gap_start_date") or None,
                resume_date=_f("resume_date") or None,
                total_days=float(td) if td not in (None, "") else None,
                fx_per_week=float(_f("fx_per_week", 5) or 5),
                remaining_mode=str(_f("remaining_mode", "same_d") or "same_d"),
                custom_remaining_n=float(cn) if cn not in (None, "") else None,
                custom_remaining_d=float(cd) if cd not in (None, "") else None,
            )
            # ensure attribute access in template works (dataclass)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        return templates.TemplateResponse(
            request=request, name="gap.html",
            context={"current_user": user, "result": result, "error": error},
        )

    # ==================================================================
    # Fractionation pattern
    # ==================================================================
    @app.get("/fractionation", response_class=HTMLResponse)
    async def frac_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="fractionation.html",
            context={"current_user": user, "result": None, "error": None, "patterns": None},
        )

    @app.post("/fractionation", response_class=HTMLResponse)
    async def frac_calc(
        request: Request,
        target_bed: float = Form(...),
        ab: float = Form(10.0),
        n_list: str = Form("5,10,15,20,25,30,35"),
    ):
        user = _need(request)
        if not user:
            return _login()
        error = None
        patterns = None
        try:
            from app.calculations.bed import alternative_patterns, solve_dose_for_bed
            ns = [float(x.strip()) for x in n_list.split(",") if x.strip()]
            patterns = alternative_patterns(target_bed, ab, ns)
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="fractionation.html",
            context={
                "current_user": user, "error": error, "patterns": patterns,
                "result": {"target_bed": target_bed, "ab": ab, "n_list": n_list},
            },
        )

    # ==================================================================
    # Equivalent square / MU / Units
    # ==================================================================
    @app.get("/eqsquare", response_class=HTMLResponse)
    async def eq_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="eqsquare.html",
            context={"current_user": user, "result": None, "error": None},
        )

    @app.post("/eqsquare", response_class=HTMLResponse)
    async def eq_calc(
        request: Request,
        mode: str = Form("rect"),
        length: float = Form(0),
        width: float = Form(0),
        diameter: float = Form(0),
    ):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import equivalent_square, equivalent_square_circular
        error = None
        result = None
        try:
            if mode == "circle":
                result = equivalent_square_circular(diameter)
            else:
                result = equivalent_square(length, width)
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="eqsquare.html",
            context={"current_user": user, "result": result, "error": error},
        )

    @app.get("/mu", response_class=HTMLResponse)
    async def mu_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            request=request, name="mu.html",
            context={"current_user": user, "result": None, "error": None},
        )

    @app.post("/mu", response_class=HTMLResponse)
    async def mu_calc(request: Request):
        user = _need(request)
        if not user:
            return _login()
        form = await request.form()
        modality = str(form.get("modality") or "photon_ssd")
        error = None
        result = None
        try:
            from app.calculations import utils_extra as ue
            dose = float(form.get("dose_cgy") or 0)
            out = float(form.get("output_cgy_mu") or 1)
            if modality == "photon_ssd":
                result = ue.mu_photon_ssd(
                    dose, out,
                    sc=float(form.get("sc") or 1),
                    sp=float(form.get("sp") or 1),
                    tmr_or_pdd=float(form.get("tmr_or_pdd") or 1),
                    sad_factor=float(form.get("sad_factor") or 1),
                    wedge=float(form.get("wedge") or 1),
                    tray=float(form.get("tray") or 1),
                    other=float(form.get("other") or 1),
                )
            elif modality == "photon_sad":
                result = ue.mu_photon_sad(
                    dose, out,
                    sc=float(form.get("sc") or 1),
                    sp=float(form.get("sp") or 1),
                    tmr=float(form.get("tmr") or 1),
                    inv_square=float(form.get("inv_square") or 1),
                    wedge=float(form.get("wedge") or 1),
                    tray=float(form.get("tray") or 1),
                    other=float(form.get("other") or 1),
                )
            else:
                result = ue.mu_electron(
                    dose, out,
                    applicator_factor=float(form.get("applicator_factor") or 1),
                    cutout_factor=float(form.get("cutout_factor") or 1),
                    ssdf=float(form.get("ssdf") or 1),
                    other=float(form.get("other") or 1),
                )
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="mu.html",
            context={"current_user": user, "result": result, "error": error},
        )

    @app.get("/units", response_class=HTMLResponse)
    async def units_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import UNIT_OPTIONS
        return templates.TemplateResponse(
            request=request, name="units.html",
            context={
                "current_user": user, "result": None, "error": None,
                "unit_options": UNIT_OPTIONS,
            },
        )

    @app.post("/units", response_class=HTMLResponse)
    async def units_calc(
        request: Request,
        value: float = Form(...),
        category: str = Form("dose"),
        from_unit: str = Form("Gy"),
        to_unit: str = Form("cGy"),
    ):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import convert_units, UNIT_OPTIONS
        error = None
        result = None
        try:
            result = convert_units(value, from_unit, to_unit, category)
        except Exception as e:
            error = str(e)
        return templates.TemplateResponse(
            request=request, name="units.html",
            context={
                "current_user": user, "result": result, "error": error,
                "unit_options": UNIT_OPTIONS,
            },
        )

    # ==================================================================
    # OAR / normal-tissue EQD2 constraints library (no calculation)
    # Developer: add / edit / delete
    # ==================================================================
    def _is_dev(user) -> bool:
        if not user:
            return False
        role = (getattr(user, "role", "") or "").lower()
        return role in ("developer", "admin")

    @app.get("/nt-constraints", response_class=HTMLResponse)
    async def nt_page(request: Request):
        user = _need(request)
        if not user:
            return _login()
        from app.calculations.utils_extra import load_constraints
        msg = request.query_params.get("msg") or ""
        return templates.TemplateResponse(
            request=request, name="nt_constraints.html",
            context={
                "current_user": user,
                "constraints": load_constraints(),
                "can_edit": _is_dev(user),
                "message": msg,
                "error": None,
                "edit_row": None,
                "edit_index": None,
            },
        )

    @app.post("/nt-constraints/add")
    async def nt_add(
        request: Request,
        organ: str = Form(...),
        endpoint: str = Form(""),
        eqd2_gy: float = Form(...),
        ab: float = Form(3.0),
        notes: str = Form(""),
    ):
        user = _need(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        from app.calculations.utils_extra import load_constraints, save_constraints
        rows = load_constraints()
        rows.append({
            "organ": organ.strip(),
            "endpoint": endpoint.strip(),
            "eqd2_gy": float(eqd2_gy),
            "ab": float(ab),
            "notes": notes.strip(),
        })
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+added", 303)

    @app.post("/nt-constraints/edit")
    async def nt_edit(
        request: Request,
        index: int = Form(...),
        organ: str = Form(...),
        endpoint: str = Form(""),
        eqd2_gy: float = Form(...),
        ab: float = Form(3.0),
        notes: str = Form(""),
    ):
        user = _need(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        from app.calculations.utils_extra import load_constraints, save_constraints
        rows = load_constraints()
        if index < 0 or index >= len(rows):
            raise HTTPException(400, "Invalid constraint index")
        rows[index] = {
            "organ": organ.strip(),
            "endpoint": endpoint.strip(),
            "eqd2_gy": float(eqd2_gy),
            "ab": float(ab),
            "notes": notes.strip(),
        }
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+updated", 303)

    @app.post("/nt-constraints/delete")
    async def nt_delete(request: Request, index: int = Form(...)):
        user = _need(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        from app.calculations.utils_extra import load_constraints, save_constraints
        rows = load_constraints()
        if index < 0 or index >= len(rows):
            raise HTTPException(400, "Invalid constraint index")
        rows.pop(index)
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+deleted", 303)

    print("fix_utils: all utility routes registered")
    return True
