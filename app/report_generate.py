"""Generate dosimetry PDF on demand — never stores report in Supabase or DB."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, List, Optional

from fastapi import Request, Form
from fastapi.responses import Response, RedirectResponse, JSONResponse

COOKIE = "dosepro_session"

# Dedicated path — avoids conflicts with GET /reports and /reports/{rid}/...
GENERATE_PATH = "/generate-dosimetry-pdf"


def _user(request: Request):
    try:
        from app.auth import get_user_by_token
        return get_user_by_token(request.cookies.get(COOKIE))
    except Exception:
        return None


def _machine(linac_id: str):
    linac_id = str(linac_id or "").strip()
    if not linac_id:
        return None, ""
    try:
        from app.models import get_linac
        m = get_linac(linac_id)
        if m:
            return m, getattr(m, "name", linac_id) or linac_id
    except Exception:
        pass
    try:
        from app.models import list_linacs
        for m in list_linacs() or []:
            if str(getattr(m, "id", "")) == linac_id:
                return m, getattr(m, "name", linac_id) or linac_id
    except Exception:
        pass
    return None, linac_id


def _records(linac_id: str, report_date: str) -> List[Any]:
    rows: List[Any] = []
    try:
        from app.models import list_output_records
        rows = list(list_output_records(linac_id=linac_id, report_date=report_date) or [])
        if not rows:
            for r in list_output_records(linac_id=linac_id) or []:
                if (getattr(r, "date_time", "") or "").startswith(report_date):
                    rows.append(r)
    except Exception as e:
        print("report_generate records:", e)
    if not rows:
        try:
            from app import repo
            if hasattr(repo, "list_outputs"):
                for r in repo.list_outputs() or []:
                    if str(getattr(r, "linac_id", "")) != linac_id:
                        continue
                    if report_date and not (getattr(r, "date_time", "") or "").startswith(report_date):
                        continue
                    rows.append(r)
        except Exception:
            pass
    return rows


def _pdf_bytes(machine_name: str, report_date: str, created_by: str, notes: str, records: List[Any]) -> bytes:
    try:
        from app.reports import build_report_pdf
        from app.models import Report

        # Ephemeral Report object only for PDF layout — NOT saved anywhere
        rep = Report(
            id="ephemeral",
            linac_id="",
            linac_name=machine_name or "—",
            report_date=report_date,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by or "",
            title="Absolute Dosimetry — %s — %s" % (machine_name or "Machine", report_date),
            modality="mixed",
            measurement_ids=[],
            notes=notes or "",
            summary={"count": len(records)},
        )
        return build_report_pdf(rep, records)
    except Exception as e:
        print("build_report_pdf failed, using simple PDF:", e)

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "ABSOLUTE DOSIMETRY REPORT")
    c.setFont("Helvetica", 10)
    y = 770
    for line in [
        "Machine: %s" % (machine_name or "—"),
        "Date: %s" % report_date,
        "Created by: %s" % (created_by or "—"),
        "Notes: %s" % (notes or "—"),
        "Measurements: %d" % len(records),
    ]:
        c.drawString(50, y, line[:95])
        y -= 16
    y -= 10
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "#  Energy  Modality  Measured  Status")
    y -= 14
    c.setFont("Helvetica", 9)
    for i, r in enumerate(records[:40], 1):
        line = "%d  %s  %s  %s  %s" % (
            i,
            getattr(r, "energy", "") or "—",
            getattr(r, "modality", "") or "—",
            getattr(r, "measured_output_cGy_MU", "") or "—",
            getattr(r, "status", "") or "—",
        )
        c.drawString(50, y, line[:95])
        y -= 12
        if y < 60:
            break
    c.setFont("Helvetica", 8)
    c.drawString(50, 40, 'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS')
    c.save()
    return buf.getvalue()


def register_report_generate(app, templates=None):
    """Register POST /generate-dosimetry-pdf and legacy /reports/generate."""

    # Remove old handlers
    paths = {GENERATE_PATH, "/reports/generate"}
    app.router.routes[:] = [
        r for r in list(app.router.routes)
        if getattr(r, "path", None) not in paths
    ]

    async def _generate(request: Request, linac_id: str, report_date: str, notes: str, report_section: str):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", status_code=303)

        linac_id = str(linac_id or "").strip()
        report_date = str(report_date or "").strip()[:10]
        notes = str(notes or "")
        section = str(report_section or "linac").strip() or "linac"

        if not linac_id or not report_date:
            return RedirectResponse(
                "/reports?section=%s&msg=Machine+and+date+are+required" % section,
                status_code=303,
            )

        _m, name = _machine(linac_id)
        if not name:
            name = linac_id

        by = getattr(user, "full_name", None) or getattr(user, "username", "") or ""
        records = _records(linac_id, report_date)

        try:
            pdf = _pdf_bytes(name, report_date, by, notes, records)
        except Exception as e:
            print("PDF generate error:", e)
            return RedirectResponse(
                "/reports?section=%s&msg=PDF+failed:+%s"
                % (section, str(e).replace(" ", "+")[:60]),
                status_code=303,
            )

        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (name or "machine"))[:40]
        fname = "dosimetry_%s_%s.pdf" % (safe_name, report_date)
        # IMPORTANT: return PDF only — nothing is written to Supabase
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=%s" % fname,
                "Cache-Control": "no-store",
            },
        )

    @app.post(GENERATE_PATH)
    async def generate_dosimetry_pdf(
        request: Request,
        linac_id: str = Form(...),
        report_date: str = Form(...),
        notes: str = Form(""),
        report_section: str = Form("linac"),
    ):
        return await _generate(request, linac_id, report_date, notes, report_section)

    # Legacy path still works if something posts to old action
    @app.post("/reports/generate")
    async def generate_legacy(
        request: Request,
        linac_id: str = Form(...),
        report_date: str = Form(...),
        notes: str = Form(""),
        report_section: str = Form("linac"),
    ):
        return await _generate(request, linac_id, report_date, notes, report_section)

    @app.get("/generate-pdf-ping")
    async def generate_ping():
        return JSONResponse({
            "ok": True,
            "path": GENERATE_PATH,
            "stores_in_supabase": False,
        })

    # Put generate routes first
    gen_paths = {GENERATE_PATH, "/reports/generate", "/generate-pdf-ping"}
    ours = [r for r in list(app.router.routes) if getattr(r, "path", None) in gen_paths]
    rest = [r for r in list(app.router.routes) if getattr(r, "path", None) not in gen_paths]
    app.router.routes[:] = ours + rest

    print("report_generate: %s registered (no storage)" % GENERATE_PATH)
    return True
