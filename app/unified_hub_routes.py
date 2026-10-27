"""Unified History and Reports hubs — 4 subsections; brachy includes source QA."""
from __future__ import annotations

from datetime import datetime
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"

HISTORY_SECTIONS = ("linac", "brachy", "daily_qa", "mechanical_qa")
REPORT_SECTIONS = ("linac", "brachy", "daily_qa", "mechanical_qa")

HUB_PATHS = ("/history", "/output-history", "/qa-history", "/reports", "/qa-reports", "/hub-ping")


def register_unified_hubs(app, templates):
    for path in HUB_PATHS:
        app.router.routes[:] = [
            r for r in list(app.router.routes)
            if getattr(r, "path", None) != path
        ]

    def _user(request: Request):
        try:
            from app.auth import get_user_by_token
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _login():
        return RedirectResponse("/login", status_code=303)

    def _tpl(request, name, **ctx):
        ctx.setdefault("current_user", _user(request))
        try:
            return templates.TemplateResponse(request=request, name=name, context=ctx)
        except TypeError:
            ctx["request"] = request
            try:
                return templates.TemplateResponse(name, ctx)
            except TypeError:
                return templates.TemplateResponse(name, context=ctx)

    def _machine_meta():
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
        except Exception as e:
            print("hub machine meta:", e)
        return meta

    def _linac_objects(brachy_only=None):
        out = []
        try:
            from app.models import list_linacs
            for m in list_linacs() or []:
                cat = (getattr(m, "category", "") or "ct_linac").lower()
                is_b = cat == "brachy" or "brachy" in cat
                if brachy_only is True and not is_b:
                    continue
                if brachy_only is False and is_b:
                    continue
                out.append(m)
        except Exception as e:
            print("hub linacs:", e)
        return out

    def _is_brachy_record(r, meta):
        lid = str(getattr(r, "linac_id", None) or (r.get("linac_id") if isinstance(r, dict) else "") or "")
        if lid in meta:
            return meta[lid]["is_brachy"]
        mod = str(getattr(r, "modality", None) or (r.get("modality") if isinstance(r, dict) else "") or "").lower()
        return "brachy" in mod or mod in ("hdr", "ldr", "pdr", "source")

    def _output_records(section):
        meta = _machine_meta()
        rows = []
        try:
            from app import repo
            rows = list(repo.list_outputs() or [])
        except Exception:
            try:
                from app.models import list_output_records
                rows = list(list_output_records() or [])
            except Exception as e:
                print("hub outputs:", e)
        want_brachy = section == "brachy"
        out = []
        for r in rows:
            is_b = _is_brachy_record(r, meta)
            if want_brachy and not is_b:
                continue
            if not want_brachy and is_b:
                continue
            out.append(r)
        return out

    def _reports(section):
        # placeholder list from memory if available
        return []

    def _qa_rows(kind, linac_id=None):
        try:
            from app.qa_results_store import list_qa_results
            return list_qa_results(kind=kind, linac_id=linac_id) or []
        except Exception as e:
            print("hub qa_rows:", e)
            return []

    @app.get("/hub-ping")
    async def hub_ping():
        return JSONResponse({
            "ok": True,
            "history_sections": list(HISTORY_SECTIONS),
            "report_sections": list(REPORT_SECTIONS),
            "brachy_includes_source_qa": True,
        })

    @app.get("/history", response_class=HTMLResponse)
    async def history_hub(request: Request):
        user = _user(request)
        if not user:
            return _login()
        section = (request.query_params.get("section") or "linac").strip().lower()
        if section not in HISTORY_SECTIONS:
            if section in ("output", "dosimetry"):
                section = "linac"
            elif section == "qa":
                section = "daily_qa"
            else:
                section = "linac"
        linac_id = (request.query_params.get("linac_id") or "").strip() or None
        records, qa_rows = [], []
        if section in ("linac", "brachy"):
            records = _output_records(section)
            if section == "brachy":
                qa_rows = _qa_rows("brachy_source", linac_id)
        elif section == "daily_qa":
            qa_rows = _qa_rows("daily", linac_id)
        else:
            qa_rows = _qa_rows("mechanical", linac_id)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "history.html",
            section=section,
            records=records,
            qa_rows=qa_rows,
            message=msg,
        )

    @app.get("/output-history")
    async def out_hist_redir():
        return RedirectResponse("/history?section=linac", status_code=303)

    @app.get("/qa-history")
    async def qa_hist_redir(request: Request):
        kind = (request.query_params.get("kind") or "daily").lower()
        section = "mechanical_qa" if kind == "mechanical" else "daily_qa"
        return RedirectResponse("/history?section=" + section, status_code=303)

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

        reports, linacs, qa_rows, machines = [], [], [], []
        week_start = datetime.utcnow().strftime("%Y-%m-%d")

        if section in ("linac", "brachy"):
            reports = _reports(section)
            linacs = _linac_objects(brachy_only=(section == "brachy"))
            if not linacs:
                linacs = _linac_objects(brachy_only=None)
            if section == "brachy":
                qa_rows = _qa_rows("brachy_source")[:80]
        elif section == "daily_qa":
            qa_rows = _qa_rows("daily")[:80]
            machines = _linac_objects(brachy_only=False) or _linac_objects(None)
            try:
                from app.qa_results_store import week_bounds
                week_start = week_bounds(week_start)[0]
            except Exception:
                pass
        else:
            qa_rows = _qa_rows("mechanical")[:80]
            machines = _linac_objects(brachy_only=False) or _linac_objects(None)

        msg = (request.query_params.get("msg") or "").replace("+", " ")
        return _tpl(
            request, "reports_hub.html",
            section=section,
            reports=reports,
            linacs=linacs,
            machines=machines,
            qa_rows=qa_rows,
            week_start=week_start,
            message=msg,
        )

    @app.get("/qa-reports")
    async def qa_rep_redir():
        return RedirectResponse("/reports?section=daily_qa", status_code=303)

    print("unified_hub_routes: /history + /reports (brachy source QA included)")
    return True
