"""
Data access: Supabase when configured, else in-memory models.
Call these from routes instead of touching dicts directly where possible.
"""

from __future__ import annotations
from typing import List, Optional
from app.db import use_db, sb_select, sb_get, sb_upsert, sb_delete, sb_insert
from app.models import (
    Detector, Linac, Beam, ToleranceTable, OutputRecord, CalcProfile, Report, Department,
    add_detector as mem_add_det, get_detector as mem_get_det, list_detectors as mem_list_det,
    delete_detector as mem_del_det,
    add_linac as mem_add_linac, get_linac as mem_get_linac, list_linacs as mem_list_linac,
    delete_linac as mem_del_linac,
    add_beam as mem_add_beam, get_beam as mem_get_beam, list_beams as mem_list_beam,
    delete_beam as mem_del_beam, update_beam as mem_update_beam,
    add_tolerance as mem_add_tol, get_tolerance as mem_get_tol, list_tolerances as mem_list_tol,
    delete_tolerance as mem_del_tol,
    add_output_record as mem_add_out, list_output_records as mem_list_out, get_output_record as mem_get_out,
    add_calc_profile as mem_add_prof, list_calc_profiles as mem_list_prof, get_default_calc_profile as mem_default_prof,
    get_calc_profile as mem_get_prof, update_calc_profile as mem_upd_prof,
    add_report as mem_add_rep, list_reports as mem_list_rep, get_report as mem_get_rep,
    get_department as mem_get_dept, update_department as mem_upd_dept,
)


# ---------- Detectors ----------

def list_detectors() -> List[Detector]:
    if not use_db():
        return mem_list_det()
    rows = sb_select("detectors", order="name")
    return [Detector(**{
        "id": r["id"], "name": r["name"], "detector_type": r["detector_type"],
        "serial_number": r.get("serial_number") or "",
        "calibration_factor": r["calibration_factor"],
        "calibration_quality": r.get("calibration_quality") or "Co-60",
        "calibration_date": r.get("calibration_date"),
        "calibration_lab": r.get("calibration_lab"),
        "next_due_date": r.get("next_due_date"),
        "notes": r.get("notes") or "",
        "unit": r.get("unit") or "Gy/nC",
    }) for r in rows]


def get_detector(det_id: str) -> Optional[Detector]:
    if not use_db():
        return mem_get_det(det_id)
    r = sb_get("detectors", det_id)
    if not r:
        return None
    return Detector(
        id=r["id"], name=r["name"], detector_type=r["detector_type"],
        serial_number=r.get("serial_number") or "",
        calibration_factor=r["calibration_factor"],
        calibration_quality=r.get("calibration_quality") or "Co-60",
        calibration_date=r.get("calibration_date"),
        calibration_lab=r.get("calibration_lab"),
        next_due_date=r.get("next_due_date"),
        notes=r.get("notes") or "", unit=r.get("unit") or "Gy/nC",
    )


def save_detector(d: Detector) -> Detector:
    if not use_db():
        mem_add_det(d)
        return d
    sb_upsert("detectors", {
        "id": d.id, "name": d.name, "detector_type": d.detector_type,
        "serial_number": d.serial_number, "calibration_factor": d.calibration_factor,
        "calibration_quality": d.calibration_quality, "calibration_date": d.calibration_date,
        "calibration_lab": d.calibration_lab, "next_due_date": d.next_due_date,
        "notes": d.notes, "unit": d.unit,
    })
    return d


def delete_detector(det_id: str) -> bool:
    if not use_db():
        return mem_del_det(det_id)
    return sb_delete("detectors", det_id)


# ---------- Machines ----------

def list_machines() -> List[Linac]:
    if not use_db():
        return mem_list_linac()
    rows = sb_select("machines", order="name")
    return [Linac(
        id=r["id"], name=r["name"], manufacturer=r.get("manufacturer") or "",
        model=r.get("model") or "", serial_number=r.get("serial_number") or "",
        location=r.get("location") or "", notes=r.get("notes") or "",
    ) for r in rows]


def get_machine(mid: str) -> Optional[Linac]:
    if not use_db():
        return mem_get_linac(mid)
    r = sb_get("machines", mid)
    if not r:
        return None
    return Linac(
        id=r["id"], name=r["name"], manufacturer=r.get("manufacturer") or "",
        model=r.get("model") or "", serial_number=r.get("serial_number") or "",
        location=r.get("location") or "", notes=r.get("notes") or "",
    )


def save_machine(m: Linac) -> Linac:
    if not use_db():
        mem_add_linac(m)
        return m
    sb_upsert("machines", {
        "id": m.id, "name": m.name, "manufacturer": m.manufacturer,
        "model": m.model, "serial_number": m.serial_number,
        "location": m.location, "notes": m.notes,
    })
    return m


def delete_machine(mid: str) -> bool:
    if not use_db():
        return mem_del_linac(mid)
    # beams cascade in SQL
    return sb_delete("machines", mid)


# ---------- Beams ----------

def list_beams(machine_id: Optional[str] = None, modality: Optional[str] = None) -> List[Beam]:
    if not use_db():
        return mem_list_beam(linac_id=machine_id, modality=modality)
    filters = {}
    if machine_id:
        filters["machine_id"] = machine_id
    if modality:
        filters["modality"] = modality
    rows = sb_select("beams", filters or None, order="nominal_energy")
    out = []
    for r in rows:
        out.append(Beam(
            id=r["id"], linac_id=r["machine_id"], modality=r["modality"],
            nominal_energy=r["nominal_energy"],
            measurement_depth_cm=r["measurement_depth_cm"],
            pdd=r.get("pdd") or 1.0, k_Q=r.get("k_q") or 1.0,
            quality_index=r.get("quality_index"),
            ssd_cm=r.get("ssd_cm") or 100.0, field_size=r.get("field_size") or "10x10",
            nominal_output_cGy_MU=r.get("nominal_output_cgy_mu") or 1.0,
            notes=r.get("notes") or "",
        ))
    return out


def get_beam(bid: str) -> Optional[Beam]:
    if not use_db():
        return mem_get_beam(bid)
    r = sb_get("beams", bid)
    if not r:
        return None
    return Beam(
        id=r["id"], linac_id=r["machine_id"], modality=r["modality"],
        nominal_energy=r["nominal_energy"], measurement_depth_cm=r["measurement_depth_cm"],
        pdd=r.get("pdd") or 1.0, k_Q=r.get("k_q") or 1.0,
        quality_index=r.get("quality_index"),
        ssd_cm=r.get("ssd_cm") or 100.0, field_size=r.get("field_size") or "10x10",
        nominal_output_cGy_MU=r.get("nominal_output_cgy_mu") or 1.0,
        notes=r.get("notes") or "",
    )


def save_beam(b: Beam) -> Beam:
    if not use_db():
        mem_add_beam(b)
        return b
    sb_upsert("beams", {
        "id": b.id, "machine_id": b.linac_id, "modality": b.modality,
        "nominal_energy": b.nominal_energy, "measurement_depth_cm": b.measurement_depth_cm,
        "pdd": b.pdd, "k_q": b.k_Q, "quality_index": b.quality_index,
        "ssd_cm": b.ssd_cm, "field_size": b.field_size,
        "nominal_output_cgy_mu": b.nominal_output_cGy_MU, "notes": b.notes,
    })
    return b


def delete_beam(bid: str) -> bool:
    if not use_db():
        return mem_del_beam(bid)
    return sb_delete("beams", bid)


# ---------- Output records ----------

def save_output(rec: OutputRecord) -> OutputRecord:
    if not use_db():
        mem_add_out(rec)
        return rec
    sb_upsert("output_records", {
        "id": rec.id, "machine_id": rec.linac_id, "beam_id": rec.beam_id,
        "modality": rec.modality, "energy": rec.energy,
        "date_time": rec.date_time,
        "measured_output_cgy_mu": rec.measured_output_cGy_MU,
        "tuned_output_cgy_mu": rec.tuned_output_cGy_MU,
        "tuning_performed": rec.tuning_performed,
        "detector_id": rec.detector_id,
        "k_tp": rec.k_TP, "k_pol": rec.k_pol, "k_s": rec.k_s, "k_q": rec.k_Q,
        "notes": rec.notes, "physicist": rec.physicist,
        "nominal_output_cgy_mu": rec.nominal_output_cGy_MU,
        "status": rec.status,
        "raw_readings": rec.raw_readings or [],
        "average_reading_nc": rec.average_reading_nC,
        "tpr20_10": rec.tpr20_10,
        "saved_for_report": rec.saved_for_report,
    })
    return rec


def list_outputs(machine_id: Optional[str] = None, report_date: Optional[str] = None,
                 saved_only: bool = False) -> List[OutputRecord]:
    if not use_db():
        return mem_list_out(linac_id=machine_id, report_date=report_date, saved_only=saved_only)
    filters = {}
    if machine_id:
        filters["machine_id"] = machine_id
    rows = sb_select("output_records", filters or None, order="date_time", desc=True)
    out = []
    for r in rows:
        dt = r.get("date_time") or ""
        if report_date and not str(dt).startswith(report_date):
            continue
        if saved_only and not r.get("saved_for_report"):
            continue
        out.append(OutputRecord(
            id=r["id"], linac_id=r["machine_id"], beam_id=r.get("beam_id") or "",
            modality=r["modality"], energy=r["energy"], date_time=str(dt),
            measured_output_cGy_MU=r["measured_output_cgy_mu"],
            tuned_output_cGy_MU=r.get("tuned_output_cgy_mu"),
            tuning_performed=bool(r.get("tuning_performed")),
            detector_id=r.get("detector_id"),
            k_TP=r.get("k_tp") or 1.0, k_pol=r.get("k_pol") or 1.0,
            k_s=r.get("k_s") or 1.0, k_Q=r.get("k_q") or 1.0,
            notes=r.get("notes") or "", physicist=r.get("physicist") or "",
            nominal_output_cGy_MU=r.get("nominal_output_cgy_mu") or 1.0,
            status=r.get("status") or "unknown",
            raw_readings=list(r.get("raw_readings") or []),
            average_reading_nC=r.get("average_reading_nc"),
            tpr20_10=r.get("tpr20_10"),
            saved_for_report=bool(r.get("saved_for_report")),
        ))
    return out


def delete_output(rid: str) -> bool:
    if not use_db():
        from app.models import _OUTPUT_RECORDS
        if rid in _OUTPUT_RECORDS:
            del _OUTPUT_RECORDS[rid]
            return True
        return False
    return sb_delete("output_records", rid)


# ---------- Department ----------

def get_department() -> Department:
    if not use_db():
        return mem_get_dept()
    r = sb_get("department", "dept")
    if not r:
        return mem_get_dept()
    return Department(
        name=r.get("name") or "", hospital=r.get("hospital") or "",
        address=r.get("address") or "", city=r.get("city") or "",
        country=r.get("country") or "", phone=r.get("phone") or "",
        email=r.get("email") or "", head_physicist=r.get("head_physicist") or "",
        logo_url=r.get("logo_url") or "", notes=r.get("notes") or "",
    )


def save_department(**kwargs) -> Department:
    if not use_db():
        return mem_upd_dept(**kwargs)
    current = get_department()
    for k, v in kwargs.items():
        if hasattr(current, k):
            setattr(current, k, v)
    sb_upsert("department", {
        "id": "dept", "name": current.name, "hospital": current.hospital,
        "address": current.address, "city": current.city, "country": current.country,
        "phone": current.phone, "email": current.email,
        "head_physicist": current.head_physicist, "logo_url": current.logo_url,
        "notes": current.notes,
    })
    return current
