"""QA history, reports, session PDF, weekly Daily QA PDF."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

COOKIE = "dosepro_session"


def mount_qa_history(app, templates):
    from app.auth import get_user_by_token, PERM_HISTORY_VIEW
    from app.qa_results_store import (
        list_qa_results, get_qa_result, delete_qa_result, week_bounds,
    )
    from app.qa_pdf import build_qa_session_pdf, build_weekly_daily_qa_pdf

    router = APIRouter(tags=["qa-history"])

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _login():
        return RedirectResponse("/login", status_code=303)

    def _tpl(request, name, **ctx):
        ctx["request"] = request
        try:
            return templates.TemplateResponse(request=request, name=name, context=ctx)
        except TypeError:
            return templates.TemplateResponse(name, ctx)

    def _machines():
        out = []
        try:
            from app.models import list_linacs
            for m in list_linacs() or []:
                out.append({"id": str(m.id), "name": m.name})
        except Exception:
            pass
        return out

    paths = {
        "/qa-history", "/qa-reports",
        "/qa-history/{rid}/pdf", "/qa-history/{rid}/delete",
        "/qa-reports/weekly", "/qa-reports/weekly.pdf",
    }
    # strip old
    app.router.routes[:] = [
        r for r in list(app.router.routes)
        if getattr(r, "path", None) not in (
            "/qa-history", "/qa-reports", "/qa-reports/weekly", "/qa-reports/weekly.pdf",
        )
        and not str(getattr(r, "path", "")).startswith("/qa-history/")
    ]

    @router.get("/qa-history", response_class=HTMLResponse)
    async def qa_history(request: Request):
        user = _user(request)
        if not user:
            return _login()
        kind = (request.query_params.get("kind") or "").strip() or None
        linac_id = (request.query_params.get("linac_id") or "").strip() or None
        rows = list_qa_results(kind=kind, linac_id=linac_id)
        return _tpl(
            request, "qa_history.html",
            current_user=user,
            rows=rows,
            kind=kind or "",
            linac_id=linac_id or "",
            machines=_machines(),
            message=(request.query_params.get("msg") or "").replace("+", " "),
        )

    @router.get("/qa-reports", response_class=HTMLResponse)
    async def qa_reports(request: Request):
        user = _user(request)
        if not user:
            return _login()
        rows = list_qa_results()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        mon, sun = week_bounds(today)
        return _tpl(
            request, "qa_reports.html",
            current_user=user,
            rows=rows[:50],
            machines=_machines(),
            week_start=mon,
            week_end=sun,
            message=(request.query_params.get("msg") or "").replace("+", " "),
        )

    @router.get("/qa-history/{rid}/pdf")
    async def qa_session_pdf(request: Request, rid: str):
        user = _user(request)
        if not user:
            return _login()
        session = get_qa_result(rid)
        if not session:
            raise HTTPException(404, "QA session not found")
        pdf = build_qa_session_pdf(session)
        kind = session.get("kind") or "qa"
        fname = "qa_%s_%s.pdf" % (kind, (session.get("performed_at") or "")[:10])
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=%s" % fname},
        )

    @router.post("/qa-history/{rid}/delete")
    async def qa_delete(request: Request, rid: str):
        user = _user(request)
        if not user:
            return _login()
        if (getattr(user, "role", "") or "").lower() not in ("developer", "admin"):
            raise HTTPException(403, "Only developer or admin can delete")
        delete_qa_result(rid)
        return RedirectResponse("/qa-history?msg=Deleted", status_code=303)

    @router.get("/qa-reports/weekly", response_class=HTMLResponse)
    async def weekly_form(request: Request):
        return RedirectResponse("/qa-reports", status_code=303)

    @router.post("/qa-reports/weekly.pdf")
    async def weekly_pdf(
        request: Request,
        week_day: str = Form(...),
        linac_id: str = Form(""),
    ):
        user = _user(request)
        if not user:
            return _login()
        week_start, week_end = week_bounds(week_day.strip()[:10])
        lid = (linac_id or "").strip() or None
        sessions = list_qa_results(
            kind="daily",
            linac_id=lid,
            date_from=week_start,
            date_to=week_end,
        )
        # chronological for report
        sessions = list(reversed(sessions))
        name = None
        if lid:
            for m in _machines():
                if m["id"] == lid:
                    name = m["name"]
                    break
        pdf = build_weekly_daily_qa_pdf(
            sessions, week_start, week_end, linac_name=name,
        )
        fname = "daily_qa_week_%s_%s.pdf" % (week_start, week_end)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=%s" % fname},
        )

    app.include_router(router)
    print("qa_history_routes: history + reports + PDFs mounted")
    return True
