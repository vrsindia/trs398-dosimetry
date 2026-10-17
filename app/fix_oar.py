"""OAR constraints library — conventional + 1/2/3/5 fraction dose limits."""
from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "dosepro_session"


def register_fix_oar(app, templates):
    from app.auth import get_user_by_token
    from app.calculations.utils_extra import (
        load_constraints, save_constraints, constraint_from_form,
    )

    paths = {
        "/nt-constraints", "/nt-constraints/add",
        "/nt-constraints/edit", "/nt-constraints/delete",
    }
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in paths
    ]

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _is_dev(user) -> bool:
        if not user:
            return False
        return (getattr(user, "role", "") or "").lower() in ("developer", "admin")

    @app.get("/nt-constraints", response_class=HTMLResponse)
    async def oar_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        msg = request.query_params.get("msg") or ""
        return templates.TemplateResponse(
            request=request, name="nt_constraints.html",
            context={
                "current_user": user,
                "constraints": load_constraints(),
                "can_edit": _is_dev(user),
                "message": msg.replace("+", " "),
                "error": None,
            },
        )

    @app.post("/nt-constraints/add")
    async def oar_add(
        request: Request,
        organ: str = Form(...),
        endpoint: str = Form(""),
        metric: str = Form("Dmax"),
        conventional_gy: str = Form(""),
        fx1_gy: str = Form(""),
        fx2_gy: str = Form(""),
        fx3_gy: str = Form(""),
        fx5_gy: str = Form(""),
        notes: str = Form(""),
    ):
        user = _user(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        rows = load_constraints()
        rows.append(constraint_from_form(
            organ, endpoint, metric,
            conventional_gy, fx1_gy, fx2_gy, fx3_gy, fx5_gy, notes,
        ))
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+added", 303)

    @app.post("/nt-constraints/edit")
    async def oar_edit(
        request: Request,
        index: int = Form(...),
        organ: str = Form(...),
        endpoint: str = Form(""),
        metric: str = Form("Dmax"),
        conventional_gy: str = Form(""),
        fx1_gy: str = Form(""),
        fx2_gy: str = Form(""),
        fx3_gy: str = Form(""),
        fx5_gy: str = Form(""),
        notes: str = Form(""),
    ):
        user = _user(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        rows = load_constraints()
        if index < 0 or index >= len(rows):
            raise HTTPException(400, "Invalid index")
        rows[index] = constraint_from_form(
            organ, endpoint, metric,
            conventional_gy, fx1_gy, fx2_gy, fx3_gy, fx5_gy, notes,
        )
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+updated", 303)

    @app.post("/nt-constraints/delete")
    async def oar_delete(request: Request, index: int = Form(...)):
        user = _user(request)
        if not user or not _is_dev(user):
            raise HTTPException(403, "Developer only")
        rows = load_constraints()
        if index < 0 or index >= len(rows):
            raise HTTPException(400, "Invalid index")
        rows.pop(index)
        save_constraints(rows)
        return RedirectResponse("/nt-constraints?msg=Constraint+deleted", 303)

    print("fix_oar: OAR constraints routes registered")
    return True
