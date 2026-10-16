"""Patch health + wire critical save/list paths to Supabase repo."""

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from app.db import status as db_status, use_db
from app.auth import get_user_by_token, PERM_HISTORY_VIEW
from app import repo
from app.reports import create_report_from_date, build_report_pdf
from app.models import get_report, list_reports

COOKIE = "dosepro_session"


def register_storage_hooks(app, templates):
    # Override /health
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/health"]
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
        }

    # Override output-history list to use repo
    to_remove = [r for r in list(app.router.routes)
                 if getattr(r, "path", None) == "/output-history"
                 and "GET" in (getattr(r, "methods", set()) or set())]
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/output-history", response_class=HTMLResponse)
    async def out_hist(request: Request):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_HISTORY_VIEW):
            return RedirectResponse("/login", 303)
        records = repo.list_outputs()
        return templates.TemplateResponse(
            request=request, name="output_history.html",
            context={"records": records, "current_user": user},
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
