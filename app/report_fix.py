"""Reliable report generate + PDF download (overrides fragile handlers)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse, Response, HTMLResponse

COOKIE = "dosepro_session"


def register_report_fix(app, templates):
    from app.auth import get_user_by_token

    # Drop competing generate/pdf routes so ours win (first-match after prepend)
    drop = {"/reports/generate"}
    kept = []
    pdf_routes = []
    for r in list(app.router.routes):
        p = getattr(r, "path", None)
        if p == "/reports/generate":
            continue
        if p == "/reports/{rid}/pdf":
            pdf_routes.append(r)
            continue
        kept.append(r)
    app.router.routes[:] = kept  # re-add pdf after our new one

    def _user(request: Request):
        try:
            return get_user_by_token(request.cookies.get(COOKIE))
        except Exception:
            return None

    def _login():
        return RedirectResponse("/login", status_code=303)

    def _resolve_machine(linac_id: str):
        linac_id = str(linac_id or "").strip()
        if not linac_id:
            return None
        try:
            from app.models import get_linac
            m = get_linac(linac_id)
            if m:
                return m
        except Exception:
            pass
        try:
            from app.models import list_linacs
            for m in list_linacs() or []:
                if str(getattr(m, "id", "")) == linac_id:
                    return m
        except Exception:
            pass
        try:
            from app import repo
            if hasattr(repo, "get_machine"):
                m = repo.get_machine(linac_id)
                if m:
                    return m
        except Exception:
            pass
        return None

    def _list_records(linac_id: str, report_date: str):
        rows = []
        try:
            from app.models import list_output_records
            rows = list_output_records(linac_id=linac_id, report_date=report_date) or []
            if not rows:
                # broader: all for machine, filter by date prefix manually
                all_m = list_output_records(linac_id=linac_id) or []
                rows = [
                    r for r in all_m
                    if (getattr(r, "date_time", "") or "").startswith(report_date)
                ]
        except Exception as e:
            print("report_fix list_output_records:", e)
        if not rows:
            try:
                from app import repo
                if hasattr(repo, "list_outputs"):
                    for r in repo.list_outputs() or []:
                        if str(getattr(r, "linac_id", "")) != linac_id:
                            continue
                        dt = getattr(r, "date_time", "") or ""
                        if report_date and not dt.startswith(report_date):
                            continue
                        rows.append(r)
            except Exception as e:
                print("report_fix repo outputs:", e)
        return rows

    def _create_report(linac_id, report_date, created_by, notes="", modality="mixed"):
        from app.models import Report, add_report, _new_id

        machine = _resolve_machine(linac_id)
        if not machine:
            return None, "Machine not found. Add or select a valid machine."

        name = getattr(machine, "name", None) or linac_id
        records = _list_records(linac_id, report_date)
        title = "Absolute Dosimetry — %s — %s" % (name, report_date)
        rep = Report(
            id=_new_id(),
            linac_id=str(linac_id),
            linac_name=name,
            report_date=report_date,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by or "",
            title=title,
            modality=modality or "mixed",
            measurement_ids=[getattr(r, "id", "") for r in records if getattr(r, "id", None)],
            notes=notes or "",
            summary={"count": len(records)},
        )
        try:
            add_report(rep)
        except Exception as e:
            print("add_report:", e)
            return None, "Could not save report: %s" % e
        return rep, None

    def _build_pdf(rep, records):
        try:
            from app.reports import build_report_pdf
            return build_report_pdf(rep, records or [])
        except Exception as e:
            print("build_report_pdf error:", e)
            # Minimal PDF fallback
            from io import BytesIO
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 800, getattr(rep, "title", "DOSE pro Report") or "DOSE pro Report")
            c.setFont("Helvetica", 10)
            y = 770
            c.drawString(50, y, "Machine: %s" % (getattr(rep, "linac_name", "") or ""))
            y -= 16
            c.drawString(50, y, "Date: %s" % (getattr(rep, "report_date", "") or ""))
            y -= 16
            c.drawString(50, y, "By: %s" % (getattr(rep, "created_by", "") or ""))
            y -= 24
            c.drawString(50, y, "Measurements: %d" % len(records or []))
            y -= 20
            for r in (records or [])[:25]:
                line = "%s  %s  %s" % (
                    getattr(r, "energy", ""),
                    getattr(r, "modality", ""),
                    getattr(r, "measured_output_cGy_MU", ""),
                )
                c.drawString(50, y, line[:90])
                y -= 14
                if y < 60:
                    break
            c.setFont("Helvetica", 8)
            c.drawString(50, 40, 'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS')
            c.save()
            return buf.getvalue()

    @app.post("/reports/generate")
    async def reports_generate(
        request: Request,
        linac_id: str = Form(...),
        report_date: str = Form(...),
        notes: str = Form(""),
        report_section: str = Form(""),
    ):
        user = _user(request)
        if not user:
            return _login()

        linac_id = str(linac_id).strip()
        report_date = str(report_date).strip()[:10]
        notes = str(notes or "")
        section = str(report_section or "linac").strip() or "linac"

        if not linac_id or not report_date:
            return RedirectResponse(
                "/reports?section=%s&msg=Machine+and+date+required" % section,
                status_code=303,
            )

        by = getattr(user, "full_name", None) or getattr(user, "username", "") or ""
        modality = "brachy" if section == "brachy" else "mixed"
        rep, err = _create_report(linac_id, report_date, by, notes, modality=modality)
        if err or not rep:
            msg = (err or "Could not create report").replace(" ", "+")
            return RedirectResponse(
                "/reports?section=%s&msg=%s" % (section, msg),
                status_code=303,
            )

        # Always stream PDF immediately (do not depend on second GET finding report)
        records = _list_records(linac_id, report_date)
        try:
            pdf = _build_pdf(rep, records)
        except Exception as e:
            print("pdf build failed:", e)
            return RedirectResponse(
                "/reports?section=%s&msg=PDF+build+failed:+%s"
                % (section, str(e).replace(" ", "+")[:80]),
                status_code=303,
            )

        fname = "dosimetry_%s_%s.pdf" % (
            (getattr(rep, "linac_name", "machine") or "machine").replace(" ", "_")[:30],
            report_date,
        )
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=%s" % fname},
        )

    @app.get("/reports/{rid}/pdf")
    async def report_pdf_get(request: Request, rid: str):
        user = _user(request)
        if not user:
            return _login()
        from app.models import get_report

        rep = get_report(rid)
        if not rep:
            raise HTTPException(404, "Report not found. Generate the report again.")
        records = _list_records(rep.linac_id, rep.report_date)
        # also try by measurement ids
        if not records and getattr(rep, "measurement_ids", None):
            try:
                from app.models import get_output_record
                for mid in rep.measurement_ids:
                    r = get_output_record(mid)
                    if r:
                        records.append(r)
            except Exception:
                pass
        pdf = _build_pdf(rep, records)
        fname = "report_%s.pdf" % (rep.report_date or rid)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=%s" % fname},
        )

    # Prepend our routes so they match first
    our = [r for r in list(app.router.routes) if getattr(r, "path", None) in (
        "/reports/generate", "/reports/{rid}/pdf",
    )]
    rest = [r for r in list(app.router.routes) if getattr(r, "path", None) not in (
        "/reports/generate", "/reports/{rid}/pdf",
    )]
    app.router.routes[:] = our + rest

    print("report_fix: /reports/generate + /reports/{rid}/pdf registered")
    return True
