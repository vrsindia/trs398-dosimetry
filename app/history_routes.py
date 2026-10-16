"""Output history delete (admin/developer only) and PDF report download."""

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, Response
from app.models import list_output_records, get_report, list_output_records as list_recs
from app.auth import get_user_by_token, PERM_HISTORY_VIEW
from app.reports import build_report_pdf

COOKIE = "dosepro_session"

# Access to underlying store for delete
from app.models import _OUTPUT_RECORDS


def register_history_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _login():
        return RedirectResponse("/login", 303)

    @app.post("/output-history/{rid}/delete")
    async def delete_output(request: Request, rid: str):
        user = _user(request)
        if not user:
            return _login()
        if user.role not in ("developer", "admin"):
            raise HTTPException(403, "Only developer or admin can delete output history")
        if rid in _OUTPUT_RECORDS:
            del _OUTPUT_RECORDS[rid]
        return RedirectResponse("/output-history", 303)

    @app.get("/reports/{rid}/pdf")
    async def report_pdf(request: Request, rid: str):
        user = _user(request)
        if not user or not user.has(PERM_HISTORY_VIEW):
            return _login()
        rep = get_report(rid)
        if not rep:
            raise HTTPException(404)
        records = list_recs(linac_id=rep.linac_id, report_date=rep.report_date)
        try:
            pdf_bytes = build_report_pdf(rep, records)
        except Exception as e:
            raise HTTPException(500, f"PDF generation failed: {e}")
        filename = f"dosepro_{rep.linac_name.replace(' ', '_')}_{rep.report_date}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # After generate, redirect to PDF download
    # Override is handled by updating generate to redirect to pdf
