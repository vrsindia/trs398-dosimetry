"""Render entrypoint: uvicorn app.bootstrap:app --host 0.0.0.0 --port $PORT"""
import traceback
from datetime import datetime
from io import BytesIO

from fastapi import Request, Form
from fastapi.responses import Response, RedirectResponse, JSONResponse, HTMLResponse

from app.main import app, templates

try:
    from app.auth_supabase import hydrate_users_from_supabase, patch_auth_for_supabase
    n = hydrate_users_from_supabase()
    if n:
        print("Loaded %d users from Supabase" % n)
    else:
        from app.auth import seed_users
        seed_users()
        print("seed_users (in-memory defaults)")
    patch_auth_for_supabase()
except Exception as e:
    print("auth_supabase:", e)
    try:
        from app.auth import seed_users
        seed_users()
    except Exception:
        pass

try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
    print("force_utils OK")
except Exception as e:
    print("FORCE_UTILS FAILED:", e)
    traceback.print_exc()

for _label, _mod, _fn in [
    ("extra_routes", "app.extra_routes", "register_extra_routes"),
    ("history_routes", "app.history_routes", "register_history_routes"),
    ("storage_hooks", "app.storage_hooks", "register_storage_hooks"),
    ("report_view", "app.report_view_route", "register_report_view"),
    ("linac_category", "app.linac_add_patch", "register_linac_category_routes"),
    ("branding_routes", "app.branding_routes", "register_branding_routes"),
    ("mr_energy_patch", "app.mr_energy_patch", "register_mr_energy_patch"),
    ("activity_routes", "app.activity_routes", "register_activity_routes"),
]:
    try:
        mod = __import__(_mod, fromlist=[_fn])
        getattr(mod, _fn)(app, templates)
        print(_label, "OK")
    except Exception as e:
        print(_label + ":", e)

try:
    from app.department_routes import register_department_routes
    register_department_routes(app, templates)
    print("department_routes OK")
except Exception as e:
    print("department_routes:", e)

try:
    from app.fix_utils import register_fix_utils
    register_fix_utils(app, templates)
    print("fix_utils OK")
except Exception as e:
    print("fix_utils FAILED:", e)

try:
    from app.fix_fractionation import register_fix_fractionation
    register_fix_fractionation(app, templates)
except Exception as e:
    print("fix_fractionation:", e)

try:
    from app.fix_oar import register_fix_oar
    register_fix_oar(app, templates)
except Exception as e:
    print("fix_oar:", e)

try:
    from app.fix_calc import register_fix_calc
    register_fix_calc(app, templates)
    print("fix_calc OK")
except Exception as e:
    print("fix_calc FAILED:", e)
    traceback.print_exc()

try:
    from app.users_routes import register_users_routes
    register_users_routes(app, templates)
    print("users_routes OK")
except Exception as e:
    print("users_routes FAILED:", e)
    traceback.print_exc()

try:
    from app.qa_mount import mount_qa
    mount_qa(app, templates)
    print("qa_mount OK")
except Exception as e:
    print("qa_mount FAILED:", e)
    traceback.print_exc()

try:
    from app.qa_history_routes import mount_qa_history
    mount_qa_history(app, templates)
    print("qa_history OK")
except Exception as e:
    print("qa_history FAILED:", e)
    traceback.print_exc()

try:
    from app.unified_hub_routes import register_unified_hubs
    register_unified_hubs(app, templates)
    print("unified_hubs OK")
except Exception as e:
    print("unified_hubs FAILED:", e)
    traceback.print_exc()

# ---------------------------------------------------------------------------
# INLINE PDF generate — always registered here (no separate import required)
# Does NOT store anything in Supabase.
# ---------------------------------------------------------------------------
COOKIE = "dosepro_session"


def _pdf_user(request: Request):
    try:
        from app.auth import get_user_by_token
        return get_user_by_token(request.cookies.get(COOKIE))
    except Exception:
        return None


def _pdf_machine_name(linac_id: str) -> str:
    try:
        from app.models import get_linac, list_linacs
        m = get_linac(linac_id)
        if m:
            return getattr(m, "name", None) or linac_id
        for m in list_linacs() or []:
            if str(getattr(m, "id", "")) == str(linac_id):
                return getattr(m, "name", None) or linac_id
    except Exception:
        pass
    return linac_id or "Machine"


def _pdf_records(linac_id: str, report_date: str):
    rows = []
    try:
        from app.models import list_output_records
        rows = list(list_output_records(linac_id=linac_id, report_date=report_date) or [])
        if not rows:
            for r in list_output_records(linac_id=linac_id) or []:
                if (getattr(r, "date_time", "") or "").startswith(report_date):
                    rows.append(r)
    except Exception as e:
        print("inline pdf records:", e)
    return rows


def _build_simple_pdf(machine_name, report_date, created_by, notes, records):
    try:
        from app.reports import build_report_pdf
        from app.models import Report
        rep = Report(
            id="tmp",
            linac_id="",
            linac_name=machine_name,
            report_date=report_date,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by or "",
            title="Absolute Dosimetry — %s — %s" % (machine_name, report_date),
            modality="mixed",
            measurement_ids=[],
            notes=notes or "",
            summary={"count": len(records)},
        )
        return build_report_pdf(rep, records)
    except Exception as e:
        print("full PDF failed, simple:", e)
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "ABSOLUTE DOSIMETRY REPORT")
    c.setFont("Helvetica", 10)
    y = 770
    for line in [
        "Machine: %s" % machine_name,
        "Date: %s" % report_date,
        "By: %s" % (created_by or "—"),
        "Notes: %s" % (notes or "—"),
        "Measurements: %d" % len(records),
    ]:
        c.drawString(50, y, line[:100])
        y -= 16
    y -= 8
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Energy | Modality | Measured | Status")
    y -= 14
    c.setFont("Helvetica", 9)
    for r in records[:40]:
        c.drawString(50, y, "%s | %s | %s | %s" % (
            getattr(r, "energy", "—"),
            getattr(r, "modality", "—"),
            getattr(r, "measured_output_cGy_MU", "—"),
            getattr(r, "status", "—"),
        )[:100])
        y -= 12
        if y < 50:
            break
    c.setFont("Helvetica", 8)
    c.drawString(50, 36, 'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS')
    c.save()
    return buf.getvalue()


async def _do_generate_pdf(request: Request, linac_id: str, report_date: str, notes: str, report_section: str):
    user = _pdf_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    linac_id = str(linac_id or "").strip()
    report_date = str(report_date or "").strip()[:10]
    notes = str(notes or "")
    section = str(report_section or "linac").strip() or "linac"
    if not linac_id or not report_date:
        return RedirectResponse(
            "/reports?section=%s&msg=Machine+and+date+required" % section, 303,
        )
    name = _pdf_machine_name(linac_id)
    by = getattr(user, "full_name", None) or getattr(user, "username", "") or ""
    records = _pdf_records(linac_id, report_date)
    try:
        pdf = _build_simple_pdf(name, report_date, by, notes, records)
    except Exception as e:
        return RedirectResponse(
            "/reports?section=%s&msg=PDF+error:+%s" % (section, str(e).replace(" ", "+")[:50]),
            303,
        )
    fname = "dosimetry_%s_%s.pdf" % (
        "".join(ch if ch.isalnum() else "_" for ch in name)[:30],
        report_date,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=%s" % fname,
            "Cache-Control": "no-store",
        },
    )


# Strip any previous copies then register
for _p in (
    "/generate-dosimetry-pdf",
    "/reports/generate",
    "/api/generate-pdf",
    "/generate-pdf-ping",
):
    app.router.routes[:] = [
        r for r in list(app.router.routes) if getattr(r, "path", None) != _p
    ]


@app.post("/generate-dosimetry-pdf")
async def generate_dosimetry_pdf(
    request: Request,
    linac_id: str = Form(""),
    report_date: str = Form(""),
    notes: str = Form(""),
    report_section: str = Form("linac"),
):
    return await _do_generate_pdf(request, linac_id, report_date, notes, report_section)


@app.post("/reports/generate")
async def reports_generate_alias(
    request: Request,
    linac_id: str = Form(""),
    report_date: str = Form(""),
    notes: str = Form(""),
    report_section: str = Form("linac"),
):
    return await _do_generate_pdf(request, linac_id, report_date, notes, report_section)


@app.post("/api/generate-pdf")
async def api_generate_pdf(
    request: Request,
    linac_id: str = Form(""),
    report_date: str = Form(""),
    notes: str = Form(""),
    report_section: str = Form("linac"),
):
    return await _do_generate_pdf(request, linac_id, report_date, notes, report_section)


@app.get("/generate-pdf-ping")
async def generate_pdf_ping():
    return JSONResponse({
        "ok": True,
        "paths": [
            "/generate-dosimetry-pdf",
            "/reports/generate",
            "/api/generate-pdf",
        ],
        "stores_in_supabase": False,
        "inline": True,
    })

print("INLINE PDF generate routes registered")


@app.on_event("startup")
def _startup_rebind():
    try:
        from app.qa_mount import mount_qa
        mount_qa(app, templates)
    except Exception as e:
        print("qa_mount startup:", e)
    try:
        from app.qa_history_routes import mount_qa_history
        mount_qa_history(app, templates)
    except Exception as e:
        print("qa_history startup:", e)
    try:
        from app.unified_hub_routes import register_unified_hubs
        register_unified_hubs(app, templates)
        print("unified_hubs startup OK")
    except Exception as e:
        print("unified_hubs startup:", e)
    # Re-assert generate routes after hubs (in case something cleared them)
    try:
        paths = {
            "/generate-dosimetry-pdf",
            "/reports/generate",
            "/api/generate-pdf",
            "/generate-pdf-ping",
        }
        existing = {getattr(r, "path", None) for r in app.router.routes}
        if "/generate-dosimetry-pdf" not in existing:
            print("WARNING: generate route missing after startup hub — re-import")
            # routes already defined above stay if not stripped; hubs should not strip these
        print("generate paths present:", paths & existing)
    except Exception as e:
        print("startup generate check:", e)
