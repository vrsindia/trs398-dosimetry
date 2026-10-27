"""Tolerances library — includes Brachy source QA limits (editable here only)."""
from __future__ import annotations

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.models import (
    ToleranceTable, add_tolerance, get_tolerance, list_tolerances,
    delete_tolerance, _new_id, list_linacs,
)
from app.brachy_qa_tolerances import ensure_brachy_tolerances, BRACHY_QA_TOLS

COOKIE = "dosepro_session"
TEMPLATE = "tolerances.html"

BRACHY_PARAMS = list(BRACHY_QA_TOLS.keys())


def register_tolerances_routes(app, templates):
    for path in (
        "/tolerances", "/tolerances/add",
        "/tolerances/{tol_id}/edit", "/tolerances/{tol_id}/delete",
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

    def _can_edit(request: Request):
        u = _user(request)
        if not u:
            return None
        try:
            if u.has(PERM_LIBRARY_EDIT):
                return u
        except Exception:
            pass
        role = (getattr(u, "role", "") or "").lower()
        if role in ("developer", "admin", "physicist"):
            return u
        return None

    def _tpl(request, **ctx):
        # Always seed brachy QA rows into the library
        try:
            ensure_brachy_tolerances()
        except Exception as e:
            print("ensure_brachy_tolerances:", e)
        ctx.setdefault("current_user", _user(request))
        ctx.setdefault("tolerances", list_tolerances())
        ctx.setdefault("linacs", list_linacs())
        ctx.setdefault("brachy_params", BRACHY_PARAMS)
        ctx.setdefault("brachy_param_labels", {k: v[0] for k, v in BRACHY_QA_TOLS.items()})
        ctx.setdefault("message", "")
        ctx.setdefault("error", "")
        try:
            return templates.TemplateResponse(request=request, name=TEMPLATE, context=ctx)
        except TypeError:
            ctx["request"] = request
            return templates.TemplateResponse(TEMPLATE, ctx)

    @app.get("/tolerances", response_class=HTMLResponse)
    async def tolerances_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(request, current_user=user, message=msg)

    @app.post("/tolerances/add")
    async def tol_add(
        request: Request,
        name: str = Form(...),
        parameter: str = Form("output"),
        modality: str = Form("photon"),
        energy: str = Form(""),
        tolerance_percent: float = Form(2.0),
        action_level_percent: str = Form(""),
        baseline_value: str = Form(""),
        linac_id: str = Form(""),
        notes: str = Form(""),
    ):
        if not _can_edit(request):
            return RedirectResponse("/login", 303)
        action = None
        if str(action_level_percent).strip():
            try:
                action = float(action_level_percent)
            except Exception:
                action = None
        baseline = None
        if str(baseline_value).strip():
            try:
                baseline = float(baseline_value)
            except Exception:
                baseline = None
        # Auto-name for brachy QA params if blank-ish
        param = (parameter or "output").strip()
        mod = (modality or "photon").strip()
        if param in BRACHY_QA_TOLS:
            mod = "brachy"
            if not name.strip():
                name = BRACHY_QA_TOLS[param][0]
        tol = ToleranceTable(
            id=_new_id(),
            name=name.strip(),
            linac_id=(linac_id.strip() or None),
            modality=mod,
            energy=(energy.strip() or None),
            parameter=param,
            tolerance_percent=float(tolerance_percent),
            action_level_percent=action,
            baseline_value=baseline,
            notes=notes.strip(),
        )
        add_tolerance(tol)
        try:
            from app.db import use_db, sb_upsert
            if use_db():
                sb_upsert("tolerances", {
                    "id": tol.id, "name": tol.name, "linac_id": tol.linac_id,
                    "modality": tol.modality, "energy": tol.energy,
                    "parameter": tol.parameter,
                    "tolerance_percent": tol.tolerance_percent,
                    "action_level_percent": tol.action_level_percent,
                    "baseline_value": tol.baseline_value,
                    "notes": tol.notes,
                })
        except Exception as e:
            print("tol add supabase:", e)
        return RedirectResponse("/tolerances?msg=Tolerance+added", 303)

    @app.post("/tolerances/{tol_id}/edit")
    async def tol_edit(
        request: Request,
        tol_id: str,
        name: str = Form(...),
        parameter: str = Form("output"),
        modality: str = Form("photon"),
        energy: str = Form(""),
        tolerance_percent: float = Form(2.0),
        action_level_percent: str = Form(""),
        baseline_value: str = Form(""),
        linac_id: str = Form(""),
        notes: str = Form(""),
    ):
        if not _can_edit(request):
            return RedirectResponse("/login", 303)
        existing = get_tolerance(tol_id)
        if not existing:
            return RedirectResponse("/tolerances?msg=Not+found", 303)
        action = None
        if str(action_level_percent).strip():
            try:
                action = float(action_level_percent)
            except Exception:
                action = None
        baseline = None
        if str(baseline_value).strip():
            try:
                baseline = float(baseline_value)
            except Exception:
                baseline = None
        param = (parameter or existing.parameter or "output").strip()
        mod = (modality or existing.modality or "photon").strip()
        if param in BRACHY_QA_TOLS:
            mod = "brachy"
        tol = ToleranceTable(
            id=tol_id,
            name=name.strip(),
            linac_id=(linac_id.strip() or None),
            modality=mod,
            energy=(energy.strip() or None),
            parameter=param,
            tolerance_percent=float(tolerance_percent),
            action_level_percent=action,
            baseline_value=baseline,
            notes=notes.strip(),
        )
        add_tolerance(tol)  # overwrite same id
        try:
            from app.db import use_db, sb_upsert
            if use_db():
                sb_upsert("tolerances", {
                    "id": tol.id, "name": tol.name, "linac_id": tol.linac_id,
                    "modality": tol.modality, "energy": tol.energy,
                    "parameter": tol.parameter,
                    "tolerance_percent": tol.tolerance_percent,
                    "action_level_percent": tol.action_level_percent,
                    "baseline_value": tol.baseline_value,
                    "notes": tol.notes,
                })
        except Exception as e:
            print("tol edit supabase:", e)
        return RedirectResponse("/tolerances?msg=Tolerance+updated", 303)

    @app.post("/tolerances/{tol_id}/delete")
    async def tol_delete(request: Request, tol_id: str):
        if not _can_edit(request):
            return RedirectResponse("/login", 303)
        delete_tolerance(tol_id)
        try:
            from app.db import use_db, sb_delete
            if use_db():
                sb_delete("tolerances", tol_id)
        except Exception as e:
            print("tol delete supabase:", e)
        return RedirectResponse("/tolerances?msg=Tolerance+deleted", 303)

    print("tolerances_routes: library includes Brachy source QA")
    return True
