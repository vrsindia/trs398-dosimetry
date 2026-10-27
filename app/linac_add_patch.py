"""Linac + beam CRUD — Supabase only."""

from fastapi import Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from app.models import Linac, Beam, get_linac, get_beam, _new_id, update_beam
from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.machine_category import normalize_category
from app.machine_store import (
    save_machine_db, delete_machine_db, save_beam_db, delete_beam_db,
    hydrate_machines, supabase_configured,
    list_machines_supabase_only, list_beams_supabase_only, last_error, status_dict,
)

COOKIE = "dosepro_session"


def _user_can_edit(request: Request):
    user = get_user_by_token(request.cookies.get(COOKIE))
    if not user or not user.has(PERM_LIBRARY_EDIT):
        return None
    return user


def _user(request: Request):
    try:
        return get_user_by_token(request.cookies.get(COOKIE))
    except Exception:
        return None


def _fail_msg(prefix: str) -> str:
    err = (last_error() or "unknown").replace(" ", "+")[:140]
    return prefix + "+" + err


def register_linac_category_routes(app, templates):
    kill = {
        "/linacs", "/linacs/add", "/linacs/{linac_id}/edit", "/linacs/{linac_id}/delete",
        "/beams/add", "/beams/{beam_id}/edit", "/beams/{beam_id}/delete",
        "/machines-db-status",
    }
    to_remove = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        if path in kill:
            to_remove.append(r)
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    try:
        hydrate_machines()
    except Exception as e:
        print("hydrate_machines on register:", e)

    @app.get("/machines-db-status")
    async def machines_db_status():
        return JSONResponse(status_dict())

    @app.get("/linacs", response_class=HTMLResponse)
    async def linacs_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        db_ok = supabase_configured()
        linacs, beams = [], []
        try:
            linacs = list_machines_supabase_only()
            beams = list_beams_supabase_only()
        except Exception as e:
            msg = (msg + " Load error: " + str(e)).strip()
        if not db_ok:
            msg = (msg + " Supabase not configured.").strip()
        else:
            msg = (msg + (" Loaded %d machine(s) from Supabase." % len(linacs))).strip()
            if last_error():
                msg = (msg + " DB note: " + last_error()).strip()
        ctx = {"current_user": user, "linacs": linacs, "beams": beams, "message": msg}
        try:
            return templates.TemplateResponse(request=request, name="linacs.html", context=ctx)
        except TypeError:
            ctx["request"] = request
            return templates.TemplateResponse("linacs.html", ctx)

    @app.post("/linacs/add")
    async def linac_add(
        request: Request,
        name: str = Form(...),
        manufacturer: str = Form(""),
        model: str = Form(""),
        serial_number: str = Form(""),
        location: str = Form(""),
        notes: str = Form(""),
        category: str = Form("ct_linac"),
    ):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        if not supabase_configured():
            return RedirectResponse("/linacs?msg=Supabase+not+configured", 303)
        cat = normalize_category(category)
        kwargs = dict(
            id=_new_id(), name=name.strip(), manufacturer=manufacturer.strip(),
            model=model.strip(), serial_number=serial_number.strip(),
            location=location.strip(), notes=notes.strip(),
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        ok = save_machine_db(linac)
        msg = "Machine+saved+to+Supabase" if ok else _fail_msg("FAILED+save")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/linacs/{linac_id}/edit")
    async def linac_edit(
        request: Request,
        linac_id: str,
        name: str = Form(...),
        manufacturer: str = Form(""),
        model: str = Form(""),
        serial_number: str = Form(""),
        location: str = Form(""),
        notes: str = Form(""),
        category: str = Form("ct_linac"),
    ):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        if not supabase_configured():
            return RedirectResponse("/linacs?msg=Supabase+not+configured", 303)
        cat = normalize_category(category)
        kwargs = dict(
            id=linac_id, name=name.strip(), manufacturer=manufacturer.strip(),
            model=model.strip(), serial_number=serial_number.strip(),
            location=location.strip(), notes=notes.strip(),
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        ok = save_machine_db(linac)
        msg = "Machine+updated+in+Supabase" if ok else _fail_msg("FAILED+update")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/linacs/{linac_id}/delete")
    async def linac_delete(request: Request, linac_id: str):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        ok = delete_machine_db(linac_id)
        msg = "Machine+deleted+from+Supabase" if ok else _fail_msg("FAILED+delete")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/beams/add")
    async def beam_add(
        request: Request,
        linac_id: str = Form(...),
        modality: str = Form("photon"),
        nominal_energy: str = Form(...),
        measurement_depth_cm: float = Form(10.0),
        pdd: float = Form(1.0),
        k_Q: float = Form(1.0),
        nominal_output_cGy_MU: float = Form(1.0),
        ssd_cm: float = Form(100.0),
        field_size: str = Form("10x10"),
        quality_index: str = Form(""),
        tpr20_10_baseline: str = Form(""),
        notes: str = Form(""),
    ):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        if not supabase_configured():
            return RedirectResponse("/linacs?msg=Supabase+not+configured", 303)
        qi = None
        if str(quality_index).strip():
            try:
                qi = float(quality_index)
            except Exception:
                qi = None
        mod = (modality or "photon").lower()
        hydrate_machines()
        linac = get_linac(linac_id)
        if linac and getattr(linac, "category", "") == "mr_linac" and mod == "electron":
            return RedirectResponse("/linacs?msg=MR+Linac+has+no+electrons", 303)
        beam = Beam(
            id=_new_id(), linac_id=linac_id, modality=mod,
            nominal_energy=str(nominal_energy).strip(),
            measurement_depth_cm=float(measurement_depth_cm),
            pdd=float(pdd), k_Q=float(k_Q),
            nominal_output_cGy_MU=float(nominal_output_cGy_MU),
            ssd_cm=float(ssd_cm), field_size=str(field_size).strip() or "10x10",
            quality_index=qi, notes=str(notes).strip(),
        )
        ok = save_beam_db(beam)
        msg = "Beam+saved+to+Supabase" if ok else _fail_msg("FAILED+beam")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/beams/{beam_id}/edit")
    async def beam_edit(
        request: Request,
        beam_id: str,
        modality: str = Form("photon"),
        nominal_energy: str = Form(...),
        measurement_depth_cm: float = Form(10.0),
        pdd: float = Form(1.0),
        k_Q: float = Form(1.0),
        nominal_output_cGy_MU: float = Form(1.0),
        ssd_cm: float = Form(100.0),
        field_size: str = Form("10x10"),
        quality_index: str = Form(""),
        tpr20_10_baseline: str = Form(""),
        notes: str = Form(""),
    ):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        if not supabase_configured():
            return RedirectResponse("/linacs?msg=Supabase+not+configured", 303)
        hydrate_machines()
        existing = get_beam(beam_id)
        if not existing:
            return RedirectResponse("/linacs?msg=Beam+not+found", 303)
        qi = None
        if str(quality_index).strip():
            try:
                qi = float(quality_index)
            except Exception:
                qi = None
        mod = (modality or "photon").lower()
        updated = update_beam(
            beam_id, modality=mod, nominal_energy=str(nominal_energy).strip(),
            measurement_depth_cm=float(measurement_depth_cm), pdd=float(pdd), k_Q=float(k_Q),
            nominal_output_cGy_MU=float(nominal_output_cGy_MU), ssd_cm=float(ssd_cm),
            field_size=str(field_size).strip() or "10x10", quality_index=qi, notes=str(notes).strip(),
        )
        if updated is None:
            updated = Beam(
                id=beam_id, linac_id=getattr(existing, "linac_id", ""), modality=mod,
                nominal_energy=str(nominal_energy).strip(),
                measurement_depth_cm=float(measurement_depth_cm), pdd=float(pdd), k_Q=float(k_Q),
                nominal_output_cGy_MU=float(nominal_output_cGy_MU), ssd_cm=float(ssd_cm),
                field_size=str(field_size).strip() or "10x10", quality_index=qi, notes=str(notes).strip(),
            )
        ok = save_beam_db(updated)
        msg = "Beam+updated+in+Supabase" if ok else _fail_msg("FAILED+beam+update")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/beams/{beam_id}/delete")
    async def beam_delete(request: Request, beam_id: str):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        ok = delete_beam_db(beam_id)
        msg = "Beam+deleted+from+Supabase" if ok else _fail_msg("FAILED+beam+delete")
        return RedirectResponse("/linacs?msg=" + msg, 303)

    print("linac_add_patch: Supabase-only machines library")
