"""Unified History and Reports hubs — 4 subsections each."""
from __future__ import annotations

from datetime import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = "dosepro_session"

HISTORY_SECTIONS = ("linac", "brachy", "daily_qa", "mechanical_qa")
REPORT_SECTIONS = ("linac", "brachy", "daily_qa", "mechanical_qa")


def register_unified_hubs(app, templates):
    from app.auth import get_user_by_token

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

    def _machine_meta():
        """id -> {name, category, is_brachy}"""
        meta = {}
        try:
            from app.models import list_linacs
            for m in list_linacs() or []:
                cat = (getattr(m, "category", "") or "ct_linac").lower()
                meta[str(m.id)] = {
                    "name": m.name,
                    "category": cat,
                    "is_brachy": cat == "brachy" or "brachy" in cat,
                }
        except Exception:
            pass
        return meta

    def _machines_list(brachy_only=None):
        out = []
        for mid, info in _machine_meta().items():
            if brachy_only is True and not info["is_brachy"]:
                continue
            if brachy_only is False and info["is_brachy"]:
                continue
            out.append({"id": mid, "name": info["name"], "category": info["category"]})
        return out

    def _linac_objects(brachy_only=None):
        try:
            from app.models import list_linacs
            rows = list_linacs() or []
        except Exception:
            return []
        out = []
        for m in rows:
            cat = (getattr(m, "category", "") or "ct_linac").lower()
            is_b = cat == "brachy" or "brachy" in cat
            if brachy_only is True and not is_b:
                continue
            if brachy_only is False and is_b:
                continue
            out.append(m)
        return out

    def _is_brachy_record(r, meta):
        lid = str(getattr(r, "linac_id", "") or "")
        if lid in meta:
            return meta[lid]["is_brachy"]
        mod = (getattr(r, "modality", "") or "").lower()
        return "brachy" in mod or mod in ("hdr", "ldr", "pdr", "source")

    def _output_records(section):
        try:
            from app import repo
            records = repo.list_outputs()
        except Exception:
            try:
                from app.models import list_output_records
                records = list_output_records()
            except Exception:
                records = []
        meta = _machine_meta()
        want_brachy = section == "brachy"
        enriched = []
        for r in records:
            is_b = _is_brachy_record(r, meta)
            if want_brachy and not is_b:
                continue
            if not want_brachy and is_b:
                continue
            lid = str(getattr(r, "linac_id", "") or "")
            name = meta.get(lid, {}).get("name") or lid or "—"
            try:
                setattr(r, "machine_name", name)
            except Exception:
                pass
            enriched.append(r)
        return enriched

    def _reports(section):
        try:
            from app.models import list_reports
            rows = list_reports() or []
        except Exception:
            try:
                from app.models import _REPORTS
                rows = list(_REPORTS.values()) if isinstance(_REPORTS, dict) else list(_REPORTS)
            except Exception:
                rows = []
        meta = _machine_meta()
        want_brachy = section == "brachy"
        out = []
        for r in rows:
            lid = str(getattr(r, "linac_id", "") or "")
            is_b = False
            if lid in meta:
                is_b = meta[lid]["is_brachy"]
            else:
                mod = (getattr(r, "modality", "") or "").lower()
                title = (getattr(r, "title", "") or "").lower()
                is_b = "brachy" in mod or "brachy" in title
            if want_brachy and not is_b:
                continue
            if not want_brachy and is_b:
                continue
            out.append(r)
        return out

    def _qa_rows(kind, linac_id=None):
        try:
            from app.qa_results_store import list_qa_results
            return list_qa_results(kind=kind, linac_id=linac_id)
        except Exception as e:
            print("qa list:", e)
            return []

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
        section = (request.query_params.get("section") or "linac").strip().lower()
        if section not in HISTORY_SECTIONS:
            # map legacy
            if section in ("output", "dosimetry"):
                section = "linac"
            elif section == "qa":
                section = "daily_qa"
            else:
                section = "linac"
        linac_id = (request.query_params.get("linac_id") or "").strip() or None
        records = []
        qa_rows = []
        if section in ("linac", "brachy"):
            records = _output_records(section)
        elif section == "daily_qa":
            qa_rows = _qa_rows("daily", linac_id)
        else:
            qa_rows = _qa_rows("mechanical", linac_id)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "history.html",
            current_user=user,
            section=section,
            records=records,
            qa_rows=qa_rows,
            linac_id=linac_id or "",
            machines=_machines_list(),
            message=msg,
        )

    @app.get("/output-history", response_class=HTMLResponse)
    async def output_history_redir(request: Request):
        return RedirectResponse("/history?section=linac", status_code=303)

    @app.get("/qa-history", response_class=HTMLResponse)
    async def qa_history_redir(request: Request):
        kind = (request.query_params.get("kind") or "daily").strip()
        section = "mechanical_qa" if kind == "mechanical" else "daily_qa"
        parts = ["section=" + section]
        if request.query_params.get("linac_id"):
            parts.append("linac_id=" + request.query_params.get("linac_id"))
        if request.query_params.get("msg"):
            parts.append("msg=" + request.query_params.get("msg"))
        return RedirectResponse("/history?" + "&".join(parts), status_code=303)

    @app.get("/reports", response_class=HTMLResponse)
    async def reports_hub(request: Request):
        user = _user(request)
        if not user:
            return _login()
        section = (request.query_params.get("section") or "linac").strip().lower()
        if section not in REPORT_SECTIONS:
            if section in ("dosimetry", "output"):
                section = "linac"
            elif section == "qa":
                section = "daily_qa"
            else:
                section = "linac"

        reports = []
        linacs = []
        qa_rows = []
        machines = []
        week_start = datetime.utcnow().strftime("%Y-%m-%d")

        if section in ("linac", "brachy"):
            reports = _reports(section)
            linacs = _linac_objects(brachy_only=(section == "brachy"))
        elif section == "daily_qa":
            qa_rows = _qa_rows("daily")[:80]
            machines = _machines_list()
            try:
                from app.qa_results_store import week_bounds
                week_start, _ = week_bounds(week_start)
            except Exception:
                pass
        else:
            qa_rows = _qa_rows("mechanical")[:80]
            machines = _machines_list()

        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "reports_hub.html",
            current_user=user,
            section=section,
            reports=reports,
            linacs=linacs,
            qa_rows=qa_rows,
            machines=machines,
            week_start=week_start,
            message=msg,
        )

    @app.get("/qa-reports", response_class=HTMLResponse)
    async def qa_reports_redir(request: Request):
        return RedirectResponse("/reports?section=daily_qa", status_code=303)

    print("unified_hub_routes: 4-section History + Reports")
    return True
