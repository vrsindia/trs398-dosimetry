"""Machine-specific Daily QA + Mechanical QA — hardened registration."""
from __future__ import annotations

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"
EDIT_ROLES = {"developer", "admin", "physicist"}

QA_PATHS = [
    "/daily-qa",
    "/mechanical-qa",
    "/library/edit-checklist",
    "/library/edit-mechanical-qa",
    "/library/edit-checklist/add",
    "/library/edit-checklist/edit",
    "/library/edit-checklist/delete",
    "/library/edit-mechanical-qa/add",
    "/library/edit-mechanical-qa/edit",
    "/library/edit-mechanical-qa/delete",
    "/qa-ping",
]


def register_qa_routes(app, templates):
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

    # Strip previous QA routes (by path)
    app.router.routes[:] = [
        r for r in list(app.router.routes)
        if getattr(r, "path", None) not in QA_PATHS
    ]

    def _user(request: Request):
        try:
            tok = request.cookies.get(COOKIE)
            if not tok:
                return None
            return get_user_by_token(tok)
        except Exception:
            return None

    def _can_edit(user) -> bool:
        if not user:
            return False
        return (getattr(user, "role", "") or "").lower() in EDIT_ROLES

    def _login():
        return RedirectResponse("/login", status_code=303)

    def _machines():
        """Return list of simple dicts {id, name, category, manufacturer, model}."""
        out = []
        sources = []
        try:
            from app.models import list_linacs
            sources.append(list_linacs())
        except Exception as e:
            print("qa list_linacs:", e)
        try:
            from app.repo import list_machines
            sources.append(list_machines())
        except Exception:
            pass
        seen = set()
        for src in sources:
            if not src:
                continue
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

    def _machine(mid: str):
        mid = str(mid or "").strip()
        if not mid:
            return None
        for m in _machines():
            if m["id"] == mid:
                return m
        return None

    def _tpl(request: Request, name: str, **ctx):
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
                results.append({
                    "id": iid,
                    "label": it.get("label") or "",
                    "item_type": itype,
                    "answer": ans,
                    "status": status,
                    "display": display,
                })
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
                    unit = it.get("unit") or ""
                    display = ("%s %s" % (val, unit)).strip()
                results.append({
                    "id": iid,
                    "label": it.get("label") or "",
                    "item_type": itype,
                    "answer": raw,
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
        q = "linac_id=%s&msg=%s" % (linac_id, msg.replace(" ", "+"))
        return RedirectResponse("%s?%s" % (base, q), status_code=303)

    # ---- Daily QA ----
    @app.get("/daily-qa", response_class=HTMLResponse)
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
            current_user=user,
            machines=machines,
            linac_id=linac_id,
            machine=machine,
            items=items,
            results=None,
            overall=None,
            can_edit=_can_edit(user),
            error=None,
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
                can_edit=_can_edit(user),
                error="Please select a machine first.",
            )
        items = load_daily_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "daily_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user), error=None,
        )

    # ---- Mechanical QA ----
    @app.get("/mechanical-qa", response_class=HTMLResponse)
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
            current_user=user,
            machines=machines,
            linac_id=linac_id,
            machine=machine,
            items=items,
            results=None,
            overall=None,
            can_edit=_can_edit(user),
            error=None,
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
                can_edit=_can_edit(user),
                error="Please select a machine first.",
            )
        items = load_mech_items(linac_id)
        results, overall = _run_qa(items, form)
        return _tpl(
            request, "mechanical_qa.html",
            current_user=user, machines=machines, linac_id=linac_id,
            machine=machine, items=items, results=results, overall=overall,
            can_edit=_can_edit(user), error=None,
        )

    # ---- Editors ----
    def _editor_page(request: Request, kind: str):
        user = _user(request)
        if not user:
            return _login()
        if not _can_edit(user):
            raise HTTPException(status_code=403, detail="Only developer, admin or physicist can edit checklists")
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
            current_user=user,
            items=items,
            kind=kind,
            title=title,
            message=msg,
            machines=machines,
            linac_id=linac_id,
            machine=machine,
        )

    @app.get("/library/edit-checklist", response_class=HTMLResponse)
    async def edit_daily_get(request: Request):
        return _editor_page(request, "daily")

    @app.get("/library/edit-mechanical-qa", response_class=HTMLResponse)
    async def edit_mech_get(request: Request):
        return _editor_page(request, "mech")

    @app.post("/library/edit-checklist/add")
    async def daily_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        try:
            row = _parse_item(form)
        except ValueError as e:
            raise HTTPException(400, str(e))
        lid = row["linac_id"]
        rows = load_daily_items(lid)
        row["id"] = new_id("d")
        rows.append(row)
        save_daily_items(lid, rows)
        return _redir_editor("daily", lid, "Item added")

    @app.post("/library/edit-checklist/edit")
    async def daily_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        try:
            row = _parse_item(form)
        except ValueError as e:
            raise HTTPException(400, str(e))
        lid = row["linac_id"]
        iid = row["id"]
        rows = load_daily_items(lid)
        found = False
        for i, r in enumerate(rows):
            if str(r.get("id")) == iid:
                rows[i] = row
                found = True
                break
        if not found:
            rows.append(row)
        save_daily_items(lid, rows)
        return _redir_editor("daily", lid, "Item updated")

    @app.post("/library/edit-checklist/delete")
    async def daily_del(
        request: Request,
        id: str = Form(...),
        linac_id: str = Form(...),
    ):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        lid = str(linac_id).strip()
        rows = [r for r in load_daily_items(lid) if str(r.get("id")) != str(id)]
        save_daily_items(lid, rows)
        return _redir_editor("daily", lid, "Item deleted")

    @app.post("/library/edit-mechanical-qa/add")
    async def mech_add(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        try:
            row = _parse_item(form)
        except ValueError as e:
            raise HTTPException(400, str(e))
        lid = row["linac_id"]
        rows = load_mech_items(lid)
        row["id"] = new_id("m")
        rows.append(row)
        save_mech_items(lid, rows)
        return _redir_editor("mech", lid, "Item added")

    @app.post("/library/edit-mechanical-qa/edit")
    async def mech_edit(request: Request):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        form = await request.form()
        try:
            row = _parse_item(form)
        except ValueError as e:
            raise HTTPException(400, str(e))
        lid = row["linac_id"]
        iid = row["id"]
        rows = load_mech_items(lid)
        found = False
        for i, r in enumerate(rows):
            if str(r.get("id")) == iid:
                rows[i] = row
                found = True
                break
        if not found:
            rows.append(row)
        save_mech_items(lid, rows)
        return _redir_editor("mech", lid, "Item updated")

    @app.post("/library/edit-mechanical-qa/delete")
    async def mech_del(
        request: Request,
        id: str = Form(...),
        linac_id: str = Form(...),
    ):
        user = _user(request)
        if not user or not _can_edit(user):
            raise HTTPException(403)
        lid = str(linac_id).strip()
        rows = [r for r in load_mech_items(lid) if str(r.get("id")) != str(id)]
        save_mech_items(lid, rows)
        return _redir_editor("mech", lid, "Item deleted")

    @app.get("/qa-ping")
    async def qa_ping():
        try:
            machines = _machines()
            return JSONResponse({
                "ok": True,
                "machine_count": len(machines),
                "machines": [m["name"] for m in machines],
                "paths": QA_PATHS,
            })
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    print("qa_routes: machine-specific Daily + Mechanical QA registered (%d paths)" % len(QA_PATHS))
    return True
