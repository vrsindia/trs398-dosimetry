"""Linac add/edit + beam add/edit/delete (machine library)."""

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from app.models import (
    Linac, Beam, add_linac, get_linac, _new_id,
    add_beam, get_beam, update_beam, delete_beam,
)
from app.auth import get_user_by_token, PERM_LIBRARY_EDIT
from app.machine_category import normalize_category

COOKIE = "dosepro_session"


def _user_can_edit(request: Request):
    user = get_user_by_token(request.cookies.get(COOKIE))
    if not user or not user.has(PERM_LIBRARY_EDIT):
        return None
    return user


def register_linac_category_routes(app, templates):
    # Remove conflicting routes then re-register
    kill = {
        "/linacs/add",
        "/linacs/{linac_id}/edit",
        "/beams/add",
        "/beams/{beam_id}/edit",
        "/beams/{beam_id}/delete",
    }
    to_remove = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", set()) or set()
        if path in kill and "POST" in methods:
            to_remove.append(r)
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.post("/linacs/add")
    async def linac_add_with_category(
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
            id=_new_id(), name=name, manufacturer=manufacturer, model=model,
            serial_number=serial_number, location=location, notes=notes,
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        add_linac(linac)
        return RedirectResponse("/linacs?msg=Machine+added", 303)

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
        existing = get_linac(linac_id)
        if not existing:
            return RedirectResponse("/linacs?msg=Machine+not+found", 303)
        cat = normalize_category(category)
        kwargs = dict(
            id=linac_id,
            name=name.strip(),
            manufacturer=manufacturer.strip(),
            model=model.strip(),
            serial_number=serial_number.strip(),
            location=location.strip(),
            notes=notes.strip(),
        )
        try:
            linac = Linac(**kwargs, category=cat)
        except TypeError:
            linac = Linac(**kwargs)
            if hasattr(linac, "category"):
                linac.category = cat
        add_linac(linac)
        return RedirectResponse("/linacs?msg=Machine+updated", 303)

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
        tpr = None
        if str(tpr20_10_baseline).strip():
            try:
                tpr = float(tpr20_10_baseline)
            except Exception:
                tpr = None
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
            tpr20_10_baseline=tpr,
            notes=str(notes).strip(),
        )
        add_beam(beam)
        # Prefer repo if available (Supabase)
        try:
            from app.repo import save_beam
            save_beam(beam)
        except Exception:
            pass
        return RedirectResponse("/linacs?msg=Beam+added", 303)

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
            try:
                from app.repo import get_beam as repo_get
                existing = repo_get(beam_id)
            except Exception:
                existing = None
        if not existing:
            return RedirectResponse("/linacs?msg=Beam+not+found", 303)

        qi = None
        if str(quality_index).strip():
            try:
                qi = float(quality_index)
            except Exception:
                qi = None
        tpr = None
        if str(tpr20_10_baseline).strip():
            try:
                tpr = float(tpr20_10_baseline)
            except Exception:
                tpr = None

        mod = (modality or "photon").lower()
        linac = get_linac(getattr(existing, "linac_id", ""))
        if linac and getattr(linac, "category", "") == "mr_linac" and mod == "electron":
            return RedirectResponse("/linacs?msg=MR+Linac+has+no+electrons", 303)

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
            tpr20_10_baseline=tpr,
            notes=str(notes).strip(),
        )
        if updated is None:
            # recreate in place
            beam = Beam(
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
                tpr20_10_baseline=tpr,
                notes=str(notes).strip(),
            )
            add_beam(beam)
            updated = beam
        try:
            from app.repo import save_beam
            save_beam(updated)
        except Exception:
            pass
        return RedirectResponse("/linacs?msg=Beam+updated", 303)

    @app.post("/beams/{beam_id}/delete")
    async def beam_delete(request: Request, beam_id: str):
        if not _user_can_edit(request):
            return RedirectResponse("/login", 303)
        delete_beam(beam_id)
        try:
            from app.repo import delete_beam as repo_del
            repo_del(beam_id)
        except Exception:
            pass
        return RedirectResponse("/linacs?msg=Beam+deleted", 303)

    print("linac_add_patch: machine + beam add/edit/delete")
