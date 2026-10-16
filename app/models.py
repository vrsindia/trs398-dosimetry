"""
DOSE pro core models: detectors, linacs, beams, tolerances, calc profiles, measurements, reports.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import date, datetime
import uuid


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


@dataclass
class Department:
    name: str = "Radiation Oncology Department"
    hospital: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    phone: str = ""
    email: str = ""
    head_physicist: str = ""
    logo_url: str = ""
    notes: str = ""


_DEPARTMENT = Department()

def get_department() -> Department:
    return _DEPARTMENT

def update_department(**kwargs) -> Department:
    for k, v in kwargs.items():
        if hasattr(_DEPARTMENT, k):
            setattr(_DEPARTMENT, k, v)
    return _DEPARTMENT


@dataclass
class Detector:
    id: str
    name: str
    detector_type: str
    serial_number: str
    calibration_factor: float
    calibration_quality: str = "Co-60"
    calibration_date: Optional[str] = None
    calibration_lab: Optional[str] = None
    next_due_date: Optional[str] = None
    notes: str = ""
    unit: str = "Gy/nC"

    def is_overdue(self) -> bool:
        if not self.next_due_date:
            return False
        try:
            return date.today() > date.fromisoformat(self.next_due_date)
        except Exception:
            return False


@dataclass
class Linac:
    id: str
    name: str
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    notes: str = ""
    category: str = "ct_linac"  # ct_linac | mr_linac | brachy


@dataclass
class Beam:
    id: str
    linac_id: str
    modality: str
    nominal_energy: str
    measurement_depth_cm: float
    pdd: float = 1.0
    k_Q: float = 1.0
    quality_index: Optional[float] = None
    ssd_cm: float = 100.0
    field_size: str = "10x10"
    notes: str = ""
    nominal_output_cGy_MU: float = 1.0


@dataclass
class ToleranceTable:
    id: str
    name: str
    linac_id: Optional[str] = None
    modality: str = "photon"
    energy: Optional[str] = None
    parameter: str = "output"  # output | tpr20_10 | source_strength
    tolerance_percent: float = 2.0
    action_level_percent: Optional[float] = 3.0
    baseline_value: Optional[float] = None
    notes: str = ""


@dataclass
class CalcProfile:
    id: str
    name: str
    use_k_TP: bool = True
    use_k_pol: bool = True
    use_k_s: bool = True
    use_k_Q: bool = True
    use_electrometer_factor: bool = True
    use_k_other: bool = False
    use_pdd_correction: bool = False
    notes: str = ""
    is_default: bool = False


@dataclass
class OutputRecord:
    id: str
    linac_id: str
    beam_id: str
    modality: str
    energy: str
    date_time: str
    measured_output_cGy_MU: float
    tuned_output_cGy_MU: Optional[float] = None
    tuning_performed: bool = False
    detector_id: Optional[str] = None
    k_TP: float = 1.0
    k_pol: float = 1.0
    k_s: float = 1.0
    k_Q: float = 1.0
    notes: str = ""
    physicist: str = ""
    nominal_output_cGy_MU: float = 1.0
    status: str = "unknown"
    raw_readings: List[float] = field(default_factory=list)
    average_reading_nC: Optional[float] = None
    tpr20_10: Optional[float] = None
    saved_for_report: bool = False


@dataclass
class Report:
    id: str
    linac_id: str
    linac_name: str
    report_date: str
    created_at: str
    created_by: str
    title: str
    modality: str = "photon"
    measurement_ids: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class PendingChange:
    id: str
    entity_type: str
    entity_id: str
    action: str
    proposed_data: Dict[str, Any]
    original_data: Optional[Dict[str, Any]] = None
    requested_by: str = ""
    requested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"
    reviewed_by: str = ""
    reviewed_at: Optional[str] = None
    comment: str = ""


_DETECTORS: Dict[str, Detector] = {}
_LINACS: Dict[str, Linac] = {}
_BEAMS: Dict[str, Beam] = {}
_TOLERANCES: Dict[str, ToleranceTable] = {}
_OUTPUT_RECORDS: Dict[str, OutputRecord] = {}
_PENDING: Dict[str, PendingChange] = {}
_CALC_PROFILES: Dict[str, CalcProfile] = {}
_REPORTS: Dict[str, Report] = {}


def add_detector(det: Detector) -> Detector:
    _DETECTORS[det.id] = det
    return det

def get_detector(det_id: str) -> Optional[Detector]:
    return _DETECTORS.get(det_id)

def list_detectors() -> List[Detector]:
    return sorted(_DETECTORS.values(), key=lambda d: d.name.lower())

def delete_detector(det_id: str) -> bool:
    return _DETECTORS.pop(det_id, None) is not None


def add_linac(linac: Linac) -> Linac:
    _LINACS[linac.id] = linac
    return linac

def get_linac(linac_id: str) -> Optional[Linac]:
    return _LINACS.get(linac_id)

def list_linacs() -> List[Linac]:
    return sorted(_LINACS.values(), key=lambda l: l.name.lower())

def delete_linac(linac_id: str) -> bool:
    for bid in [b.id for b in _BEAMS.values() if b.linac_id == linac_id]:
        _BEAMS.pop(bid, None)
    return _LINACS.pop(linac_id, None) is not None


def add_beam(beam: Beam) -> Beam:
    _BEAMS[beam.id] = beam
    return beam

def get_beam(beam_id: str) -> Optional[Beam]:
    return _BEAMS.get(beam_id)

def list_beams(linac_id: Optional[str] = None, modality: Optional[str] = None) -> List[Beam]:
    beams = list(_BEAMS.values())
    if linac_id:
        beams = [b for b in beams if b.linac_id == linac_id]
    if modality:
        beams = [b for b in beams if b.modality == modality]
    return sorted(beams, key=lambda b: (b.modality, b.nominal_energy))

def delete_beam(beam_id: str) -> bool:
    return _BEAMS.pop(beam_id, None) is not None

def update_beam(beam_id: str, **kwargs) -> Optional[Beam]:
    b = _BEAMS.get(beam_id)
    if not b:
        return None
    for k, v in kwargs.items():
        if hasattr(b, k):
            setattr(b, k, v)
    return b


def add_tolerance(tol: ToleranceTable) -> ToleranceTable:
    _TOLERANCES[tol.id] = tol
    return tol

def get_tolerance(tol_id: str) -> Optional[ToleranceTable]:
    return _TOLERANCES.get(tol_id)

def list_tolerances() -> List[ToleranceTable]:
    return list(_TOLERANCES.values())

def delete_tolerance(tol_id: str) -> bool:
    return _TOLERANCES.pop(tol_id, None) is not None

def find_tolerance(modality: str, energy: Optional[str] = None,
                   linac_id: Optional[str] = None, parameter: str = "output") -> Optional[ToleranceTable]:
    candidates = [t for t in _TOLERANCES.values() if t.parameter == parameter]
    # prefer exact machine + energy + modality
    for t in candidates:
        if t.linac_id == linac_id and t.energy == energy and t.modality == modality:
            return t
    for t in candidates:
        if t.linac_id == linac_id and not t.energy and t.modality == modality:
            return t
    for t in candidates:
        if not t.linac_id and t.energy == energy and t.modality == modality:
            return t
    for t in candidates:
        if not t.linac_id and not t.energy and t.modality == modality:
            return t
    for t in candidates:
        if not t.linac_id and not t.energy:
            return t
    return None

def check_tolerance(measured: float, nominal: float, tol: Optional[ToleranceTable]) -> str:
    if not tol or nominal == 0:
        return "unknown"
    pct = abs(measured - nominal) / abs(nominal) * 100.0
    action = tol.action_level_percent if tol.action_level_percent is not None else tol.tolerance_percent * 1.5
    if pct <= tol.tolerance_percent:
        return "pass"
    if pct <= action:
        return "warning"
    return "fail"


def add_output_record(rec: OutputRecord) -> OutputRecord:
    _OUTPUT_RECORDS[rec.id] = rec
    return rec

def get_output_record(rid: str) -> Optional[OutputRecord]:
    return _OUTPUT_RECORDS.get(rid)

def list_output_records(linac_id: Optional[str] = None, report_date: Optional[str] = None,
                        saved_only: bool = False) -> List[OutputRecord]:
    rows = list(_OUTPUT_RECORDS.values())
    if linac_id:
        rows = [r for r in rows if r.linac_id == linac_id]
    if report_date:
        rows = [r for r in rows if r.date_time.startswith(report_date)]
    if saved_only:
        rows = [r for r in rows if r.saved_for_report]
    return sorted(rows, key=lambda r: r.date_time, reverse=True)


def add_calc_profile(p: CalcProfile) -> CalcProfile:
    _CALC_PROFILES[p.id] = p
    return p

def get_calc_profile(pid: str) -> Optional[CalcProfile]:
    return _CALC_PROFILES.get(pid)

def list_calc_profiles() -> List[CalcProfile]:
    return list(_CALC_PROFILES.values())

def get_default_calc_profile() -> CalcProfile:
    for p in _CALC_PROFILES.values():
        if p.is_default:
            return p
    if _CALC_PROFILES:
        return next(iter(_CALC_PROFILES.values()))
    return CalcProfile(id="default", name="Full TRS-398", is_default=True)

def update_calc_profile(pid: str, **kwargs) -> Optional[CalcProfile]:
    p = _CALC_PROFILES.get(pid)
    if not p:
        return None
    if kwargs.get("is_default"):
        for other in _CALC_PROFILES.values():
            other.is_default = False
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def add_report(rep: Report) -> Report:
    _REPORTS[rep.id] = rep
    return rep

def get_report(rid: str) -> Optional[Report]:
    return _REPORTS.get(rid)

def list_reports() -> List[Report]:
    return sorted(_REPORTS.values(), key=lambda r: r.report_date, reverse=True)


def submit_change(entity_type, entity_id, action, proposed, original, requested_by) -> PendingChange:
    pc = PendingChange(
        id=_new_id(), entity_type=entity_type, entity_id=entity_id, action=action,
        proposed_data=proposed, original_data=original, requested_by=requested_by,
    )
    _PENDING[pc.id] = pc
    return pc

def list_pending() -> List[PendingChange]:
    return [p for p in _PENDING.values() if p.status == "pending"]

def approve_change(pid: str, reviewed_by: str) -> Optional[PendingChange]:
    p = _PENDING.get(pid)
    if not p or p.status != "pending":
        return None
    p.status = "approved"
    p.reviewed_by = reviewed_by
    p.reviewed_at = datetime.utcnow().isoformat()
    data = p.proposed_data
    if p.entity_type == "detector" and p.entity_id in _DETECTORS:
        for k, v in data.items():
            if hasattr(_DETECTORS[p.entity_id], k):
                setattr(_DETECTORS[p.entity_id], k, v)
    elif p.entity_type == "beam" and p.entity_id in _BEAMS:
        for k, v in data.items():
            if hasattr(_BEAMS[p.entity_id], k):
                setattr(_BEAMS[p.entity_id], k, v)
    elif p.entity_type == "tolerance" and p.entity_id in _TOLERANCES:
        for k, v in data.items():
            if hasattr(_TOLERANCES[p.entity_id], k):
                setattr(_TOLERANCES[p.entity_id], k, v)
    elif p.entity_type == "department":
        update_department(**data)
    return p

def reject_change(pid: str, reviewed_by: str) -> Optional[PendingChange]:
    p = _PENDING.get(pid)
    if not p:
        return None
    p.status = "rejected"
    p.reviewed_by = reviewed_by
    p.reviewed_at = datetime.utcnow().isoformat()
    return p


def seed_libraries() -> None:
    if _DETECTORS:
        return
    add_detector(Detector(
        id="det-farmer-01", name="Farmer 0.6 cc", detector_type="cylindrical",
        serial_number="1234", calibration_factor=0.04521, calibration_quality="Co-60",
        calibration_date="2025-01-15", calibration_lab="SSDL", next_due_date="2026-01-15",
    ))
    add_detector(Detector(
        id="det-well-01", name="Well chamber", detector_type="well",
        serial_number="W-88", calibration_factor=1.02e8, calibration_quality="Ir-192",
        unit="Gy m2 / h / A",
    ))
    add_linac(Linac(id="linac-tb1", name="TrueBeam 1", manufacturer="Varian",
                    model="TrueBeam", category="ct_linac", location="Bunker A"))
    add_linac(Linac(id="linac-hx1", name="Halcyon 1", manufacturer="Varian",
                    model="Halcyon", category="ct_linac", location="Bunker B"))
    add_linac(Linac(id="linac-mr1", name="MR-Linac 1", manufacturer="Elekta",
                    model="Unity", category="mr_linac", location="Bunker C"))
    add_linac(Linac(id="mach-brachy1", name="HDR Brachy Suite", manufacturer="Elekta",
                    model="Flexitron", category="brachy", location="Brachy room"))
    add_beam(Beam(id="beam-tb1-6x", linac_id="linac-tb1", modality="photon",
                  nominal_energy="6 MV", measurement_depth_cm=10.0, pdd=0.667, k_Q=0.994,
                  nominal_output_cGy_MU=1.0))
    add_beam(Beam(id="beam-tb1-10x", linac_id="linac-tb1", modality="photon",
                  nominal_energy="10 MV", measurement_depth_cm=10.0, pdd=0.730, k_Q=0.986,
                  nominal_output_cGy_MU=1.0))
    add_beam(Beam(id="beam-tb1-9e", linac_id="linac-tb1", modality="electron",
                  nominal_energy="9 MeV", measurement_depth_cm=2.0, pdd=1.0, k_Q=0.910,
                  nominal_output_cGy_MU=1.0))
    add_tolerance(ToleranceTable(
        id="tol-out-ph", name="Photon output", modality="photon", parameter="output",
        tolerance_percent=2.0, action_level_percent=3.0))
    add_tolerance(ToleranceTable(
        id="tol-out-el", name="Electron output", modality="electron", parameter="output",
        tolerance_percent=2.0, action_level_percent=3.0))
    add_tolerance(ToleranceTable(
        id="tol-tpr", name="TPR20,10 baseline", modality="photon", parameter="tpr20_10",
        tolerance_percent=1.0, action_level_percent=2.0))
    add_tolerance(ToleranceTable(
        id="tol-brachy-sk", name="HDR source strength", modality="brachy",
        parameter="source_strength", tolerance_percent=3.0, action_level_percent=5.0,
        notes="Brachytherapy HDR only"))
    add_calc_profile(CalcProfile(
        id="prof-full", name="Full TRS-398 (all factors)", is_default=True))
