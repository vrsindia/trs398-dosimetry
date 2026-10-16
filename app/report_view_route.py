"""On-screen report view (HTML) + PDF still available."""

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import get_user_by_token, PERM_HISTORY_VIEW
from app.models import get_report, list_output_records, get_department
from app.db import use_db
from app import repo

COOKIE = "dosepro_session"


def register_report_view(app, templates):

    @app.get("/reports/{rid}/view", response_class=HTMLResponse)
    async def report_view(request: Request, rid: str):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user or not user.has(PERM_HISTORY_VIEW):
            return RedirectResponse("/login", 303)
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404)
        if use_db():
            records = repo.list_outputs(machine_id=rep.linac_id, report_date=rep.report_date)
        else:
            records = list_output_records(linac_id=rep.linac_id, report_date=rep.report_date)
        try:
            dept = get_department()
        except Exception:
            dept = None
        return templates.TemplateResponse(
            request=request, name="report_view.html",
            context={
                "report": rep, "records": records, "dept": dept, "current_user": user,
            },
        )
