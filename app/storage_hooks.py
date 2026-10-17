"""Patch health + output history (with machine names) via Supabase repo."""
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db import status as db_status
from app.auth import get_user_by_token, PERM_HISTORY_VIEW
from app import repo
from app.models import get_linac, list_linacs

COOKIE = "dosepro_session"


def register_storage_hooks(app, templates):
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) in ("/health", "/output-history")]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/health")
    async def health():
        st = db_status()
        return {
            "status": "ok",
            "app": "DOSE pro",
            "version": "1.5.0",
            "storage": st,
            "project": "GARUDA",
            "developer": "VRS DOSIMETRY SOLUTIONS",
        }

    def _machine_name(linac_id: str) -> str:
        try:
            m = repo.get_machine(linac_id) if hasattr(repo, "get_machine") else get_linac(linac_id)
            if m:
                return m.name
        except Exception:
            pass
        try:
            m = get_linac(linac_id)
            if m:
                return m.name
        except Exception:
            pass
        return linac_id or "—"

    @app.get("/output-history", response_class=HTMLResponse)
    async def out_hist(request: Request):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_HISTORY_VIEW):
            return RedirectResponse("/login", 303)
        records = repo.list_outputs()
        # Attach machine name for template
        name_cache = {}
        enriched = []
        for r in records:
            lid = getattr(r, "linac_id", "") or ""
            if lid not in name_cache:
                name_cache[lid] = _machine_name(lid)
            # setattr for template access
            try:
                r.machine_name = name_cache[lid]
                r.linac_name = name_cache[lid]
            except Exception:
                pass
            enriched.append(r)
        return templates.TemplateResponse(
            request=request, name="output_history.html",
            context={"records": enriched, "current_user": user},
        )

    @app.post("/output-history/{rid}/delete")
    async def del_out(request: Request, rid: str):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user:
            return RedirectResponse("/login", 303)
        if user.role not in ("developer", "admin"):
            raise HTTPException(403)
        repo.delete_output(rid)
        return RedirectResponse("/output-history", 303)

    return True
