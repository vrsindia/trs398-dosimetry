"""Daily QA + Mechanical QA checklists and library editors."""
from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.qa_store import (
    load_daily_items, save_daily_items,
    load_mech_items, save_mech_items,
    new_id, evaluate_numerical, evaluate_yes_no,
)

COOKIE = "dosepro_session"
EDIT_ROLES = {"developer", "admin", "physicist"}


def register_qa_routes(app, templates):
    from app.auth import get_user_by_token

    paths = {
        "/daily-qa", "/mechanical-qa",
        "/library/edit-checklist", "/library/edit-mechanical-qa",
        "/library/edit-checklist/add", "/library/edit-checklist/edit",
        "/library/edit-checklist/delete",
        "/library/edit-mechanical-qa/add", "/library/edit-mechanical-qa/edit",
        "/library/edit-mechanical-qa/delete",
    }
    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in paths
    ]

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _can_edit(user) -> bool:
        if not user:
            return False
        return (getattr(user, "role", "") or "").lower() in EDIT_ROLES

    def _login():
        return RedirectResponse("/login", 303)

    def _run_qa(items, form):
        results = []
        overall = "green"
        for it in items:
            iid = it["id"]
            if it.get("item_type") == "yes_no":
                ans = str(form.get(f"ans_{iid}") or "")
                status = evaluate_yes_no(ans)
                results.append({**it, "answer": ans, "status": status, "display": ans or "—"})
            else:
                raw = str(form.get(f"ans_{iid}") or "").strip()
                try:
                    val = float(raw) if raw != "" else None
                except ValueError:
                    val = None
                if val is None:
                    status = "yellow"
                    display = raw or "—"
                else:
                    status = evaluate_numerical(it, val)
                    display = f"{val} {it.get('unit') or ''}".strip()
                results.append({**it, "answer": raw, "status": status, "display": display})
            if status == "red":
                overall = "red"
            elif status == "yellow" and overall != "red":
                overall = "yellow"
        return results, overall

    @app.get("/daily-qa", response_class=HTMLResponse)
    async def daily_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            "daily_qa.html",
            {"request": request, "current_user": user, "items": load_daily_items(),
             "results": None, "overall": None, "can_edit": _can_edit(user)},
        )

    @app.post("/daily-qa", response_class=HTMLResponse)
    async def daily_qa_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        items = load_daily_items()
        results, overall = _run_qa(items, form)
        return templates.TemplateResponse(
            "daily_qa.html",
            {"request": request, "current_user": user, "items": items,
             "results": results, "overall": overall, "can_edit": _can_edit(user)},
        )

    @app.get("/mechanical-qa", response_class=HTMLResponse)
    async def mech_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        return templates.TemplateResponse(
            "mechanical_qa.html",
            {"request": request, "current_user": user, "items": load_mech_items(),
             "results": None, "overall": None, "can_edit": _can_edit(user)},
        )

    @app.post("/mechanical-qa", response_class=HTMLResponse)
    async def mech_qa_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        items = load_mech_items()
        results, overall = _run_qa(items, form)
        return templates.TemplateResponse(
            "mechanical_qa.html",
            {"request": request, "current_user": user, "items": items,
             "results": results, "overall": overall, "can_edit": _can_edit(user)},
        )

    def _editor_page(request, kind: str):
        user = _user(request)
        if not user:
            return _login()
        if not _can_edit(user):
            raise HTTPException(403, "Only developer, admin or physicist can edit checklists")
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        items = load_daily_items() if kind == "daily" else load_mech_items()
        title = "Edit checklist (Daily QA)" if kind == "daily" else "Edit mechanical QA"
        return templates.TemplateResponse(
            "edit_checklist.html",
            {"request": request, "current_user": user, "items": items,
             "kind": kind, "title": title, "message": msg},
        )

    @app.get("/library/edit-checklist", response_class=HTMLResponse)
    async def edit_daily_get(request: Request):
        return _editor_page(request, "daily")

    @app.get("/library/edit-mechanical-qa", response_class=HTMLResponse)
    async def edit_mech_get(request: Request):
        return _editor_page(request, "mech")

    def _parse_item(form) -> dict:
        item_type = str(form.get("item_type") or "yes_no")
        row = {
            "id": str(form.get("id") or new_id()),
            "label": str(form.get("label") or "").strip(),
            "item_type": item_type,
            "order": int(float(form.get("order") or 0)),
        }
        if not row["label"]:
            raise ValueError("Label is required")
        if item_type == "numerical":
            row["nominal"] = float(form.get("nominal") or 0)
            row["tol_ok"] = float(form.get("tol_ok") or 0)
            row["tol_warn"] = float(form.get("tol_warn") or 0)
            row["unit"] = str(form.get("unit") or "")
            row["mode"] = str(form.get("mode") or "absolute")
        return row

    @app.post("/library/edit-checklist/add")
    async def daily_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        rows = load_daily_items()
        row = _parse_item(form)
        row["id"] = new_id("d")
        rows.append(row)
        save_daily_items(rows)
        return RedirectResponse("/library/edit-checklist?msg=Item+added", 303)

    @app.post("/library/edit-checklist/edit")
    async def daily_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        iid = str(form.get("id") or "")
        rows = load_daily_items()
        row = _parse_item(form)
        row["id"] = iid
        for i, r in enumerate(rows):
            if r.get("id") == iid:
                rows[i] = row
                break
        save_daily_items(rows)
        return RedirectResponse("/library/edit-checklist?msg=Item+updated", 303)

    @app.post("/library/edit-checklist/delete")
    async def daily_del(request: Request, id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        save_daily_items([r for r in load_daily_items() if r.get("id") != id])
        return RedirectResponse("/library/edit-checklist?msg=Item+deleted", 303)

    @app.post("/library/edit-mechanical-qa/add")
    async def mech_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        rows = load_mech_items()
        row = _parse_item(form)
        row["id"] = new_id("m")
        rows.append(row)
        save_mech_items(rows)
        return RedirectResponse("/library/edit-mechanical-qa?msg=Item+added", 303)

    @app.post("/library/edit-mechanical-qa/edit")
    async def mech_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        iid = str(form.get("id") or "")
        rows = load_mech_items()
        row = _parse_item(form)
        row["id"] = iid
        for i, r in enumerate(rows):
            if r.get("id") == iid:
                rows[i] = row
                break
        save_mech_items(rows)
        return RedirectResponse("/library/edit-mechanical-qa?msg=Item+updated", 303)

    @app.post("/library/edit-mechanical-qa/delete")
    async def mech_del(request: Request, id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        save_mech_items([r for r in load_mech_items() if r.get("id") != id])
        return RedirectResponse("/library/edit-mechanical-qa?msg=Item+deleted", 303)

    print("qa_routes: daily + mechanical QA registered")
    return True
