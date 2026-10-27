"""Linac + beam CRUD with Supabase persistence."""

from fastapi import Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from app.models import Linac, Beam, get_linac, get_beam, list_linacs, list_beams, _new_id, update_beam
from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.machine_category import normalize_category
from app.machine_store import (
    save_machine_db, delete_machine_db, save_beam_db, delete_beam_db, hydrate_machines,
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


def register_linac_category_routes(app, templates):
    kill = {
        "/linacs", "/linacs/add", "/linacs/{linac_id}/edit", "/linacs/{linac_id}/delete",
        "/beams/add", "/beams/{beam_id}/edit", "/beams/{beam_id}/delete",
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

    # Load from Supabase at registration
    try:
        hydrate_machines()
    except Exception as e:
        print("hydrate_machines on register:", e)

    @app.get("/linacs", response_class=HTMLResponse)
    async def linacs_page(request: Request):
        user = _user(request)
        if not user:
            return RedirectResponse("/login", 303)
        try:
            hydrate_machines()
        except Exception as e:
            print("linacs hydrate:", e)
        msg = (request.query_params.get("msg") or "").replace("+", " ")
        ctx = {
            "current_user": user,
            "linacs": list_linacs(),
            "beams": list_beams(),
            "message": msg,
        }
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
        msg = "Machine+saved+to+Supabase" if ok else "Machine+saved+memory+only"
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
        if not get_linac(linac_id):
            # still allow update by id after hydrate
            pass
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
        msg = "Machine+updated+in+Supabase" if ok else "Machine+updated+memory+only"
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/linacs/{linac_id}/delete")
    async def linac_delete(request: Request, linac_id: str):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        delete_machine_db(linac_id)
        return RedirectResponse("/linacs?msg=Machine+deleted", 303)

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
        qi = None
        if str(quality_index).strip():
            try:
                qi = float(quality_index)
            except Exception:
                qi = None
        mod = (modality or "photon").lower()
        linac = get_linac(linac_id)
        if linac and getattr(linac, "category", "") == "mr_linac" and mod == "electron":
            return RedirectResponse("/linacs?msg=MR+Linac+has+no+electrons", 303)
        beam = Beam(
            id=_new_id(),
            linac_id=linac_id,
            modality=mod,
            nominal_energy=str(nominal_energy).strip(),
            measurement_depth_cm=float(measurement_depth_cm),
            pdd=float(pdd),
            k_Q=float(k_Q),
            nominal_output_cGy_MU=float(nominal_output_cGy_MU),
            ssd_cm=float(ssd_cm),
            field_size=str(field_size).strip() or "10x10",
            quality_index=qi,
            notes=str(notes).strip(),
        )
        ok = save_beam_db(beam)
        msg = "Beam+saved+to+Supabase" if ok else "Beam+saved+memory+only"
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
            beam_id,
            modality=mod,
            nominal_energy=str(nominal_energy).strip(),
            measurement_depth_cm=float(measurement_depth_cm),
            pdd=float(pdd),
            k_Q=float(k_Q),
            nominal_output_cGy_MU=float(nominal_output_cGy_MU),
            ssd_cm=float(ssd_cm),
            field_size=str(field_size).strip() or "10x10",
            quality_index=qi,
            notes=str(notes).strip(),
        )
        if updated is None:
            updated = Beam(
                id=beam_id,
                linac_id=getattr(existing, "linac_id", ""),
                modality=mod,
                nominal_energy=str(nominal_energy).strip(),
                measurement_depth_cm=float(measurement_depth_cm),
                pdd=float(pdd),
                k_Q=float(k_Q),
                nominal_output_cGy_MU=float(nominal_output_cGy_MU),
                ssd_cm=float(ssd_cm),
                field_size=str(field_size).strip() or "10x10",
                quality_index=qi,
                notes=str(notes).strip(),
            )
        ok = save_beam_db(updated)
        msg = "Beam+updated+in+Supabase" if ok else "Beam+updated+memory+only"
        return RedirectResponse("/linacs?msg=" + msg, 303)

    @app.post("/beams/{beam_id}/delete")
    async def beam_delete(request: Request, beam_id: str):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        delete_beam_db(beam_id)
        return RedirectResponse("/linacs?msg=Beam+deleted", 303)

    print("linac_add_patch: machines+beams ↔ Supabase")
