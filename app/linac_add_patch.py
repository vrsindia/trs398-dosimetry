"""Register linac add with category field (overrides plain add if needed)."""

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from app.models import Linac, add_linac, _new_id
from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.machine_category import normalize_category

COOKIE = "dosepro_session"


def register_linac_category_routes(app, templates):
    # Remove existing POST /linacs/add then re-add with category
    to_remove = []
    for r in list(app.router.routes):
        if getattr(r, "path", None) == "/linacs/add" and "POST" in (getattr(r, "methods", set()) or set()):
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
        # category field may or may not exist on older Linac dataclass
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        add_linac(linac)
        return RedirectResponse("/linacs", 303)
