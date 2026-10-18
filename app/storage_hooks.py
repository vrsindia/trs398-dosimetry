"""Health endpoint + output delete; history pages live on /history hub."""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.db import status as db_status
from app.auth import get_user_by_token
from app import repo

COOKIE = "dosepro_session"


def register_storage_hooks(app, templates):
    to_remove = [
        r for r in list(app.router.routes)
        if getattr(r, "path", None) in ("/health", "/output-history")
    ]
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
            "version": "1.6.0",
            "storage": st,
            "project": "GARUDA",
            "developer": "VRS DOSIMETRY SOLUTIONS",
        }

    # List page is the unified hub
    @app.get("/output-history")
    async def out_hist_redir():
        return RedirectResponse("/history?section=linac", status_code=303)

    @app.post("/output-history/{rid}/delete")
    async def del_out(request: Request, rid: str):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user:
            return RedirectResponse("/login", 303)
        if user.role not in ("developer", "admin"):
            raise HTTPException(403)
        try:
            repo.delete_output(rid)
        except Exception as e:
            print("delete_output:", e)
            try:
                from app.models import _OUTPUT_RECORDS
                if rid in _OUTPUT_RECORDS:
                    del _OUTPUT_RECORDS[rid]
            except Exception:
                pass
        return RedirectResponse("/history?section=linac&msg=Deleted", status_code=303)

    return True
