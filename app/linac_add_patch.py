"""Linac add + edit with category (machine library)."""

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from app.models import Linac, add_linac, get_linac, _new_id
from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.machine_category import normalize_category

COOKIE = "dosepro_session"


def register_linac_category_routes(app, templates):
    # Remove existing POST /linacs/add and /linacs/{id}/edit then re-add
    to_remove = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", set()) or set()
        if path == "/linacs/add" and "POST" in methods:
            to_remove.append(r)
        if path == "/linacs/{linac_id}/edit" and "POST" in methods:
            to_remove.append(r)
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.post("/linacs/add")
    async def linac_add_with_category(
        request: Request,
        name: str = Form(...),
        manufacturer: str = Form(""),
        model: str = Form(""),
        serial_number: str = Form(""),
        location: str = Form(""),
        notes: str = Form(""),
        category: str = Form("ct_linac"),
    ):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_LIBRARY_EDIT):
            return RedirectResponse("/login", 303)
        cat = normalize_category(category)
        kwargs = dict(
            id=_new_id(), name=name, manufacturer=manufacturer, model=model,
            serial_number=serial_number, location=location, notes=notes,
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        add_linac(linac)
        return RedirectResponse("/linacs?msg=Machine+added", 303)

    @app.post("/linacs/{linac_id}/edit")
    async def linac_edit(
        request: Request,
        linac_id: str,
        name: str = Form(...),
        manufacturer: str = Form(""),
        model: str = Form(""),
        serial_number: str = Form(""),
        location: str = Form(""),
        notes: str = Form(""),
        category: str = Form("ct_linac"),
    ):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_LIBRARY_EDIT):
            return RedirectResponse("/login", 303)
        existing = get_linac(linac_id)
        if not existing:
            return RedirectResponse("/linacs?msg=Machine+not+found", 303)
        cat = normalize_category(category)
        kwargs = dict(
            id=linac_id,
            name=name.strip(),
            manufacturer=manufacturer.strip(),
            model=model.strip(),
            serial_number=serial_number.strip(),
            location=location.strip(),
            notes=notes.strip(),
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        add_linac(linac)  # overwrite same id
        return RedirectResponse("/linacs?msg=Machine+updated", 303)

    print("linac_add_patch: add + edit machine routes")
