"""Unified History and Reports hubs with subsections."""
from __future__ import annotations

from datetime import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "dosepro_session"


def register_unified_hubs(app, templates):
    from app.auth import get_user_by_token, PERM_HISTORY_VIEW

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

    def _linacs():
        try:
            from app.models import list_linacs
            return list_linacs() or []
        except Exception:
            return []

    def _output_records():
        try:
            from app import repo
            records = repo.list_outputs()
        except Exception:
            try:
                from app.models import list_output_records
                records = list_output_records()
            except Exception:
                records = []
        # attach machine names
        name_cache = {}
        enriched = []
        for r in records:
            lid = getattr(r, "linac_id", "") or ""
            if lid not in name_cache:
                try:
                    from app.models import get_linac
                    m = get_linac(lid)
                    name_cache[lid] = m.name if m else lid
                except Exception:
                    name_cache[lid] = lid or "—"
            try:
                setattr(r, "machine_name", name_cache[lid])
            except Exception:
                pass
            enriched.append(r)
        return enriched

    def _reports():
        try:
            from app.models import list_reports
            return list_reports() or []
        except Exception:
            try:
                from app.models import _REPORTS
                return list(_REPORTS.values()) if isinstance(_REPORTS, dict) else list(_REPORTS)
            except Exception:
                return []

    # Strip competing page routes (keep PDF/delete under old paths)
    for path in ("/history", "/output-history", "/qa-history", "/reports", "/qa-reports"):
        app.router.routes[:] = [
            r for r in list(app.router.routes)
            if getattr(r, "path", None) != path
        ]

    @app.get("/history", response_class=HTMLResponse)
    async def history_hub(request: Request):
        user = _user(request)
        if not user:
            return _login()
        section = (request.query_params.get("section") or "output").strip().lower()
        if section not in ("output", "qa"):
            section = "output"
        kind = (request.query_params.get("kind") or "").strip() or None
        linac_id = (request.query_params.get("linac_id") or "").strip() or None
        qa_rows = []
        if section == "qa":
            try:
                from app.qa_results_store import list_qa_results
                qa_rows = list_qa_results(kind=kind, linac_id=linac_id)
            except Exception as e:
                print("history qa list:", e)
        records = _output_records() if section == "output" else []
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "history.html",
            current_user=user,
            section=section,
            records=records,
            qa_rows=qa_rows,
            kind=kind or "",
            linac_id=linac_id or "",
            machines=_machines(),
            message=msg,
        )

    @app.get("/output-history", response_class=HTMLResponse)
    async def output_history_redir(request: Request):
        return RedirectResponse("/history?section=output", status_code=303)

    @app.get("/qa-history", response_class=HTMLResponse)
    async def qa_history_redir(request: Request):
        q = request.query_params
        parts = ["section=qa"]
        if q.get("kind"):
            parts.append("kind=" + q.get("kind"))
        if q.get("linac_id"):
            parts.append("linac_id=" + q.get("linac_id"))
        if q.get("msg"):
            parts.append("msg=" + q.get("msg"))
        return RedirectResponse("/history?" + "&".join(parts), status_code=303)

    @app.get("/reports", response_class=HTMLResponse)
    async def reports_hub(request: Request):
        user = _user(request)
        if not user:
            return _login()
        section = (request.query_params.get("section") or "dosimetry").strip().lower()
        if section not in ("dosimetry", "qa"):
            section = "dosimetry"
        qa_rows = []
        week_start = datetime.utcnow().strftime("%Y-%m-%d")
        if section == "qa":
            try:
                from app.qa_results_store import list_qa_results, week_bounds
                qa_rows = list_qa_results()[:50]
                week_start, _ = week_bounds(week_start)
            except Exception as e:
                print("reports qa:", e)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "reports_hub.html",
            current_user=user,
            section=section,
            reports=_reports() if section == "dosimetry" else [],
            linacs=_linacs() if section == "dosimetry" else [],
            qa_rows=qa_rows,
            machines=_machines() if section == "qa" else [],
            week_start=week_start,
            message=msg,
        )

    @app.get("/qa-reports", response_class=HTMLResponse)
    async def qa_reports_redir(request: Request):
        return RedirectResponse("/reports?section=qa", status_code=303)

    print("unified_hub_routes: /history and /reports with subsections")
    return True
