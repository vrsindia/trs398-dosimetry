"""DOSE pro — load core, utilities, hubs, and inline PDF generate."""
import urllib.request
from pathlib import Path
from datetime import datetime
from io import BytesIO

_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "fbac98317ebcbd9c31bd85ec7815df834ceac023/app/main.py"
)

try:
    _code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
    exec(compile(_code, "app/main.py", "exec"), globals())
except Exception as _e:
    print("history load failed:", _e)
    _p = Path(__file__).resolve().parent
    _parts = [_p / ("_mp%d.txt" % i) for i in range(4)]
    if all(x.exists() for x in _parts):
        _code = "".join(x.read_text() for x in _parts)
        exec(compile(_code, str(_p / "core_app.py"), "exec"), globals())
    else:
        raise RuntimeError("Cannot load application: %s" % _e) from _e

try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
except Exception as e:
    print("force_utils:", e)

try:
    from app.qa_mount import mount_qa
    mount_qa(app, templates)
    print("main: qa_mount OK")
except Exception as e:
    print("main: qa_mount:", e)

try:
    from app.unified_hub_routes import register_unified_hubs
    register_unified_hubs(app, templates)
    print("main: unified_hubs OK")
except Exception as e:
    print("main: unified_hubs:", e)

# ---- Inline PDF generate (no Supabase storage) ----
try:
    from fastapi import Request, Form
    from fastapi.responses import Response, RedirectResponse, JSONResponse

    def _mu(request: Request):
        try:
            from app.auth import get_user_by_token
            return get_user_by_token(request.cookies.get("dosepro_session"))
        except Exception:
            return None

    def _mname(lid):
        try:
            from app.models import get_linac, list_linacs
            m = get_linac(lid)
            if m:
                return m.name or lid
            for m in list_linacs() or []:
                if str(m.id) == str(lid):
                    return m.name or lid
        except Exception:
            pass
        return lid or "Machine"

    def _recs(lid, d):
        try:
            from app.models import list_output_records
            rows = list(list_output_records(linac_id=lid, report_date=d) or [])
            if not rows:
                rows = [r for r in (list_output_records(linac_id=lid) or [])
                        if (getattr(r, "date_time", "") or "").startswith(d)]
            return rows
        except Exception:
            return []

    def _pdf(name, d, by, notes, records):
        try:
            from app.reports import build_report_pdf
            from app.models import Report
            rep = Report(
                id="tmp", linac_id="", linac_name=name, report_date=d,
                created_at=datetime.utcnow().isoformat(), created_by=by or "",
                title="Absolute Dosimetry — %s — %s" % (name, d),
                modality="mixed", measurement_ids=[], notes=notes or "",
                summary={"count": len(records)},
            )
            return build_report_pdf(rep, records)
        except Exception:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 800, "ABSOLUTE DOSIMETRY REPORT")
            c.setFont("Helvetica", 10)
            c.drawString(50, 770, "Machine: %s" % name)
            c.drawString(50, 754, "Date: %s" % d)
            c.drawString(50, 738, "By: %s" % (by or "—"))
            c.drawString(50, 722, "Measurements: %d" % len(records))
            c.setFont("Helvetica", 8)
            c.drawString(50, 40, 'DOSE pro · Project "GARUDA"')
            c.save()
            return buf.getvalue()

    async def _gen(request, linac_id, report_date, notes, report_section):
        user = _mu(request)
        if not user:
            return RedirectResponse("/login", 303)
        lid = str(linac_id or "").strip()
        d = str(report_date or "").strip()[:10]
        sec = str(report_section or "linac") or "linac"
        if not lid or not d:
            return RedirectResponse("/reports?section=%s&msg=Machine+and+date+required" % sec, 303)
        name = _mname(lid)
        by = getattr(user, "full_name", None) or getattr(user, "username", "") or ""
        records = _recs(lid, d)
        pdf = _pdf(name, d, by, str(notes or ""), records)
        fname = "dosimetry_%s_%s.pdf" % ("".join(ch if ch.isalnum() else "_" for ch in name)[:30], d)
        return Response(
            content=pdf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=%s" % fname, "Cache-Control": "no-store"},
        )

    for _path in ("/api/generate-pdf", "/generate-dosimetry-pdf", "/reports/generate", "/generate-pdf-ping"):
        app.router.routes[:] = [r for r in list(app.router.routes) if getattr(r, "path", None) != _path]

    @app.post("/api/generate-pdf")
    async def main_api_gen(request: Request, linac_id: str = Form(""), report_date: str = Form(""),
                           notes: str = Form(""), report_section: str = Form("linac")):
        return await _gen(request, linac_id, report_date, notes, report_section)

    @app.post("/generate-dosimetry-pdf")
    async def main_gen(request: Request, linac_id: str = Form(""), report_date: str = Form(""),
                       notes: str = Form(""), report_section: str = Form("linac")):
        return await _gen(request, linac_id, report_date, notes, report_section)

    @app.post("/reports/generate")
    async def main_legacy_gen(request: Request, linac_id: str = Form(""), report_date: str = Form(""),
                              notes: str = Form(""), report_section: str = Form("linac")):
        return await _gen(request, linac_id, report_date, notes, report_section)

    @app.get("/generate-pdf-ping")
    async def main_gen_ping():
        return JSONResponse({"ok": True, "via": "main.py", "stores_in_supabase": False})

    print("main: PDF generate routes OK")
except Exception as e:
    print("main: PDF generate FAILED:", e)
