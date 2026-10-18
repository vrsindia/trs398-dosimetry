"""Mount Daily QA + Mechanical QA on the FastAPI app (last include wins 404)."""
from __future__ import annotations

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"
EDIT_ROLES = {"developer", "admin", "physicist"}


def mount_qa(app, templates):
    """Include QA router. Safe to call multiple times."""
    from app.auth import get_user_by_token
    from app.qa_store import (
        load_daily_items,
        save_daily_items,
        load_mech_items,
        save_mech_items,
        new_id,
        evaluate_numerical,
        evaluate_yes_no,
    )

    router = APIRouter(tags=["qa"])

    def _user(request: Request):
        try:
            tok = request.cookies.get(COOKIE)
            if not tok:
                return None
            return get_user_by_token(tok)
        except Exception:
            return None

    def _can_edit(user):
        if not user:
            return False
        return (getattr(user, "role", "") or "").lower() in EDIT_ROLES

    def _login():
        return RedirectResponse("/login", status_code=303)

    def _machines():
        out = []
        seen = set()
        for loader in (
            lambda: __import__("app.models", fromlist=["list_linacs"]).list_linacs(),
            lambda: __import__("app.repo", fromlist=["list_machines"]).list_machines(),
        ):
            try:
                src = loader() or []
            except Exception:
                src = []
            for m in src:
                mid = str(getattr(m, "id", "") or "")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                out.append({
                    "id": mid,
                    "name": getattr(m, "name", mid) or mid,
                    "category": getattr(m, "category", "") or "",
                    "manufacturer": getattr(m, "manufacturer", "") or "",
                    "model": getattr(m, "model", "") or "",
                })
        return out

    def _machine(mid):
        mid = str(mid or "").strip()
        if not mid:
            return None
        for m in _machines():
            if m["id"] == mid:
                return m
        return None

    def _tpl(request, name, **ctx):
        ctx["request"] = request
        try:
            return templates.TemplateResponse(request=request, name=name, context=ctx)
        except TypeError:
            try:
                return templates.TemplateResponse(name, ctx)
            except TypeError:
                return templates.TemplateResponse(name, context=ctx)

    def _run_qa(items, form):
        results = []
        overall = "green"
        for it in items:
            iid = str(it.get("id") or "")
            itype = (it.get("item_type") or "yes_no").lower()
            if itype == "yes_no":
                ans = str(form.get("ans_%s" % iid) or "")
                status = evaluate_yes_no(ans)
                display = ans if ans else "—"
            else:
                raw = str(form.get("ans_%s" % iid) or "").strip()
                try:
                    val = float(raw) if raw != "" else None
                except ValueError:
                    val = None
                if val is None:
                    status = "yellow"
                    display = raw if raw else "—"
                else:
                    status = evaluate_numerical(it, val)
                    display = ("%s %s" % (val, it.get("unit") or "")).strip()
            results.append({
                "id": iid,
                "label": it.get("label") or "",
                "item_type": itype,
                "answer": form.get("ans_%s" % iid),
                "status": status,
                "display": display,
            })
            if status == "red":
                overall = "red"
            elif status == "yellow" and overall != "red":
                overall = "yellow"
        return results, overall

    def _parse_item(form):
        item_type = str(form.get("item_type") or "yes_no").strip().lower()
        if item_type not in ("yes_no", "numerical"):
            item_type = "yes_no"
        label = str(form.get("label") or "").strip()
        lid = str(form.get("linac_id") or "").strip()
        if not label:
            raise ValueError("Label is required")
        if not lid:
            raise ValueError("Machine is required")
        try:
            order = int(float(form.get("order") or 0))
        except (TypeError, ValueError):
            order = 0
        row = {
            "id": str(form.get("id") or new_id()),
            "label": label,
            "item_type": item_type,
            "order": order,
            "linac_id": lid,
        }
        if item_type == "numerical":
            row["nominal"] = float(form.get("nominal") or 0)
            row["tol_ok"] = float(form.get("tol_ok") or 0)
            row["tol_warn"] = float(form.get("tol_warn") or 0)
            row["unit"] = str(form.get("unit") or "")
            row["mode"] = str(form.get("mode") or "absolute")
        return row

    def _redir_editor(kind, linac_id, msg):
        base = "/library/edit-checklist" if kind == "daily" else "/library/edit-mechanical-qa"
        return RedirectResponse(
            "%s?linac_id=%s&msg=%s" % (base, linac_id, msg.replace(" ", "+")),
            status_code=303,
        )

    @router.get("/qa-ping")
    async def qa_ping():
        try:
            machines = _machines()
            return JSONResponse({
                "ok": True,
                "mounted": True,
                "machine_count": len(machines),
                "machines": [m["name"] for m in machines],
            })
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @router.get("/daily-qa", response_class=HTMLResponse)
    async def daily_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        machines = _machines()
        linac_id = str(request.query_params.get("linac_id") or "").strip()
        machine = _machine(linac_id) if linac_id else None
        items = load_daily_items(linac_id) if machine else []
        return _tpl(
            request, "daily_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=None, overall=None,
            can_edit=_can_edit(user), error=None,
        )

    @router.post("/daily-qa", response_class=HTMLResponse)
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
                can_edit=_can_edit(user), error="Please select a machine first.",
            )
        items = load_daily_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "daily_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user), error=None,
        )

    @router.get("/mechanical-qa", response_class=HTMLResponse)
    async def mech_qa_get(request: Request):
        user = _user(request)
        if not user:
            return _login()
        machines = _machines()
        linac_id = str(request.query_params.get("linac_id") or "").strip()
        machine = _machine(linac_id) if linac_id else None
        items = load_mech_items(linac_id) if machine else []
        return _tpl(
            request, "mechanical_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=None, overall=None,
            can_edit=_can_edit(user), error=None,
        )

    @router.post("/mechanical-qa", response_class=HTMLResponse)
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
                can_edit=_can_edit(user), error="Please select a machine first.",
            )
        items = load_mech_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "mechanical_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user), error=None,
        )

    def _editor(request, kind):
        user = _user(request)
        if not user:
            return _login()
        if not _can_edit(user):
            raise HTTPException(status_code=403, detail="Only developer, admin or physicist can edit")
        machines = _machines()
        linac_id = str(request.query_params.get("linac_id") or "").strip()
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

    @router.get("/library/edit-checklist", response_class=HTMLResponse)
    async def edit_daily_get(request: Request):
        return _editor(request, "daily")

    @router.get("/library/edit-mechanical-qa", response_class=HTMLResponse)
    async def edit_mech_get(request: Request):
        return _editor(request, "mech")

    @router.post("/library/edit-checklist/add")
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
        return _redir_editor("daily", lid, "Item added")

    @router.post("/library/edit-checklist/edit")
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
            if str(r.get("id")) == iid:
                rows[i] = row
                break
        else:
            rows.append(row)
        save_daily_items(lid, rows)
        return _redir_editor("daily", lid, "Item updated")

    @router.post("/library/edit-checklist/delete")
    async def daily_del(request: Request, id: str = Form(...), linac_id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        lid = str(linac_id).strip()
        rows = [r for r in load_daily_items(lid) if str(r.get("id")) != str(id)]
        save_daily_items(lid, rows)
        return _redir_editor("daily", lid, "Item deleted")

    @router.post("/library/edit-mechanical-qa/add")
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
        return _redir_editor("mech", lid, "Item added")

    @router.post("/library/edit-mechanical-qa/edit")
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
            if str(r.get("id")) == iid:
                rows[i] = row
                break
        else:
            rows.append(row)
        save_mech_items(lid, rows)
        return _redir_editor("mech", lid, "Item updated")

    @router.post("/library/edit-mechanical-qa/delete")
    async def mech_del(request: Request, id: str = Form(...), linac_id: str = Form(...)):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        lid = str(linac_id).strip()
        rows = [r for r in load_mech_items(lid) if str(r.get("id")) != str(id)]
        save_mech_items(lid, rows)
        return _redir_editor("mech", lid, "Item deleted")

    # Remove prior QA paths so we do not stack duplicates that shadow
    qa_paths = {
        "/daily-qa", "/mechanical-qa", "/qa-ping",
        "/library/edit-checklist", "/library/edit-mechanical-qa",
        "/library/edit-checklist/add", "/library/edit-checklist/edit",
        "/library/edit-checklist/delete",
        "/library/edit-mechanical-qa/add", "/library/edit-mechanical-qa/edit",
        "/library/edit-mechanical-qa/delete",
    }
    app.router.routes[:] = [
        r for r in list(app.router.routes)
        if getattr(r, "path", None) not in qa_paths
    ]

    app.include_router(router)
    print("qa_mount: Daily QA + Mechanical QA included")
    return True
