"""Machine-specific Daily QA + Mechanical QA routes."""
from __future__ import annotations
from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"
EDIT_ROLES = {"developer", "admin", "physicist"}

QA_PATHS = {
    "/daily-qa", "/mechanical-qa",
    "/library/edit-checklist", "/library/edit-mechanical-qa",
    "/library/edit-checklist/add", "/library/edit-checklist/edit",
    "/library/edit-checklist/delete",
    "/library/edit-mechanical-qa/add", "/library/edit-mechanical-qa/edit",
    "/library/edit-mechanical-qa/delete",
    "/qa-ping",
}


def register_qa_routes(app, templates):
    from app.auth import get_user_by_token
    from app.qa_store import (
        load_daily_items, save_daily_items,
        load_mech_items, save_mech_items,
        new_id, evaluate_numerical, evaluate_yes_no,
    )

    app.router.routes[:] = [
        r for r in app.router.routes
        if getattr(r, "path", None) not in QA_PATHS
    ]

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _can_edit(user) -> bool:
        if not user:
            return False
        return (getattr(user, "role", "") or "").lower() in EDIT_ROLES

    def _login():
        return RedirectResponse("/login", 303)

    def _machines():
        try:
            from app.models import list_linacs
            return list_linacs() or []
        except Exception:
            try:
                from app.repo import list_machines
                return list_machines() or []
            except Exception:
                return []

    def _machine(mid: str):
        if not mid:
            return None
        for m in _machines():
            if str(getattr(m, "id", "")) == str(mid):
                return m
        return None

    def _tpl(request: Request, name: str, **ctx):
        ctx.setdefault("request", request)
        try:
            return templates.TemplateResponse(request=request, name=name, context=ctx)
        except TypeError:
            return templates.TemplateResponse(name, ctx)

    def _run_qa(items, form):
        results = []
        overall = "green"
        for it in items:
            iid = it["id"]
            if it.get("item_type") == "yes_no":
                ans = str(form.get("ans_%s" % iid) or "")
                status = evaluate_yes_no(ans)
                results.append(dict(it, answer=ans, status=status, display=ans or "—"))
            else:
                raw = str(form.get("ans_%s" % iid) or "").strip()
                try:
                    val = float(raw) if raw != "" else None
                except ValueError:
                    val = None
                if val is None:
                    status = "yellow"
                    display = raw or "—"
                else:
                    status = evaluate_numerical(it, val)
                    display = ("%s %s" % (val, it.get("unit") or "")).strip()
                results.append(dict(it, answer=raw, status=status, display=display))
            if status == "red":
                overall = "red"
            elif status == "yellow" and overall != "red":
                overall = "yellow"
        return results, overall

    # ---------- Daily QA ----------
    @app.get("/daily-qa", response_class=HTMLResponse)
    async def daily_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        machines = _machines()
        linac_id = (request.query_params.get("linac_id") or "").strip()
        machine = _machine(linac_id) if linac_id else None
        items = load_daily_items(linac_id) if machine else []
        return _tpl(
            request, "daily_qa.html",
            current_user=user,
            machines=machines,
            linac_id=linac_id,
            machine=machine,
            items=items,
            results=None,
            overall=None,
            can_edit=_can_edit(user),
        )

    @app.post("/daily-qa", response_class=HTMLResponse)
    async def daily_qa_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        linac_id = str(form.get("linac_id") or "").strip()
        machines = _machines()
        machine = _machine(linac_id)
        if not machine:
            return _tpl(
                request, "daily_qa.html",
                current_user=user, machines=machines, linac_id="",
                machine=None, items=[], results=None, overall=None,
                can_edit=_can_edit(user), error="Select a machine first.",
            )
        items = load_daily_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "daily_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user),
        )

    # ---------- Mechanical QA ----------
    @app.get("/mechanical-qa", response_class=HTMLResponse)
    async def mech_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        machines = _machines()
        linac_id = (request.query_params.get("linac_id") or "").strip()
        machine = _machine(linac_id) if linac_id else None
        items = load_mech_items(linac_id) if machine else []
        return _tpl(
            request, "mechanical_qa.html",
            current_user=user,
            machines=machines,
            linac_id=linac_id,
            machine=machine,
            items=items,
            results=None,
            overall=None,
            can_edit=_can_edit(user),
        )

    @app.post("/mechanical-qa", response_class=HTMLResponse)
    async def mech_qa_post(request: Request):
        user = _user(request)
        if not user:
            return _login()
        form = await request.form()
        linac_id = str(form.get("linac_id") or "").strip()
        machines = _machines()
        machine = _machine(linac_id)
        if not machine:
            return _tpl(
                request, "mechanical_qa.html",
                current_user=user, machines=machines, linac_id="",
                machine=None, items=[], results=None, overall=None,
                can_edit=_can_edit(user), error="Select a machine first.",
            )
        items = load_mech_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "mechanical_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user),
        )

    # ---------- Editors ----------
    def _editor(request: Request, kind: str):
        user = _user(request)
        if not user:
            return _login()
        if not _can_edit(user):
            raise HTTPException(403, "Only developer, admin or physicist can edit checklists")
        machines = _machines()
        linac_id = (request.query_params.get("linac_id") or "").strip()
        machine = _machine(linac_id) if linac_id else None
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        items = []
        if machine:
            items = load_daily_items(linac_id) if kind == "daily" else load_mech_items(linac_id)
        title = "Edit checklist (Daily QA)" if kind == "daily" else "Edit mechanical QA"
        return _tpl(
            request, "edit_checklist.html",
            current_user=user, items=items, kind=kind, title=title,
            message=msg, machines=machines, linac_id=linac_id, machine=machine,
        )

    @app.get("/library/edit-checklist", response_class=HTMLResponse)
    async def edit_daily_get(request: Request):
        return _editor(request, "daily")

    @app.get("/library/edit-mechanical-qa", response_class=HTMLResponse)
    async def edit_mech_get(request: Request):
        return _editor(request, "mech")

    def _parse_item(form) -> dict:
        item_type = str(form.get("item_type") or "yes_no")
        row = {
            "id": str(form.get("id") or new_id()),
            "label": str(form.get("label") or "").strip(),
            "item_type": item_type,
            "order": int(float(form.get("order") or 0)),
            "linac_id": str(form.get("linac_id") or "").strip(),
        }
        if not row["label"]:
            raise ValueError("Label is required")
        if not row["linac_id"]:
            raise ValueError("Machine is required")
        if item_type == "numerical":
            row["nominal"] = float(form.get("nominal") or 0)
            row["tol_ok"] = float(form.get("tol_ok") or 0)
            row["tol_warn"] = float(form.get("tol_warn") or 0)
            row["unit"] = str(form.get("unit") or "")
            row["mode"] = str(form.get("mode") or "absolute")
        return row

    def _editor_redirect(kind: str, linac_id: str, msg: str):
        base = "/library/edit-checklist" if kind == "daily" else "/library/edit-mechanical-qa"
        return RedirectResponse("%s?linac_id=%s&msg=%s" % (base, linac_id, msg.replace(" ", "+")), 303)

    @app.post("/library/edit-checklist/add")
    async def daily_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        row = _parse_item(form)
        lid = row["linac_id"]
        rows = load_daily_items(lid)
        row["id"] = new_id("d")
        rows.append(row)
        save_daily_items(lid, rows)
        return _editor_redirect("daily", lid, "Item added")

    @app.post("/library/edit-checklist/edit")
    async def daily_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        row = _parse_item(form)
        lid = row["linac_id"]
        iid = row["id"]
        rows = load_daily_items(lid)
        for i, r in enumerate(rows):
            if r.get("id") == iid:
                rows[i] = row
                break
        else:
            rows.append(row)
        save_daily_items(lid, rows)
        return _editor_redirect("daily", lid, "Item updated")

    @app.post("/library/edit-checklist/delete")
    async def daily_del(request: Request, id: str = Form(...), linac_id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        rows = [r for r in load_daily_items(linac_id) if r.get("id") != id]
        save_daily_items(linac_id, rows)
        return _editor_redirect("daily", linac_id, "Item deleted")

    @app.post("/library/edit-mechanical-qa/add")
    async def mech_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        row = _parse_item(form)
        lid = row["linac_id"]
        rows = load_mech_items(lid)
        row["id"] = new_id("m")
        rows.append(row)
        save_mech_items(lid, rows)
        return _editor_redirect("mech", lid, "Item added")

    @app.post("/library/edit-mechanical-qa/edit")
    async def mech_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        row = _parse_item(form)
        lid = row["linac_id"]
        iid = row["id"]
        rows = load_mech_items(lid)
        for i, r in enumerate(rows):
            if r.get("id") == iid:
                rows[i] = row
                break
        else:
            rows.append(row)
        save_mech_items(lid, rows)
        return _editor_redirect("mech", lid, "Item updated")

    @app.post("/library/edit-mechanical-qa/delete")
    async def mech_del(request: Request, id: str = Form(...), linac_id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        rows = [r for r in load_mech_items(linac_id) if r.get("id") != id]
        save_mech_items(linac_id, rows)
        return _editor_redirect("mech", linac_id, "Item deleted")

    @app.get("/qa-ping")
    async def qa_ping():
        machines = _machines()
        return JSONResponse({
            "ok": True,
            "machines": [getattr(m, "name", str(m)) for m in machines],
            "machine_count": len(machines),
        })

    print("qa_routes: machine-specific Daily + Mechanical QA registered")
    return True
