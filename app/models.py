"""
Core data models + approval workflow for library edits.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import date, datetime
import uuid
import copy


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Department Details
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Linac & Beam
# ---------------------------------------------------------------------------

@dataclass
class Linac:
    id: str
    name: str
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    notes: str = ""


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


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------

@dataclass
class ToleranceTable:
    id: str
    name: str
    linac_id: Optional[str] = None
    modality: str = "photon"
    energy: Optional[str] = None
    parameter: str = "output"
    tolerance_percent: float = 2.0
    action_level_percent: Optional[float] = 3.0
    notes: str = ""


# ---------------------------------------------------------------------------
# Output Record
# ---------------------------------------------------------------------------

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
    nominal_output_cGy_MU: float = 1.0   # expected / reference
    status: str = "unknown"              # pass | warning | fail


# ---------------------------------------------------------------------------
# Pending Change (approval workflow)
# ---------------------------------------------------------------------------

@dataclass
class PendingChange:
    id: str
    entity_type: str          # detector | linac | beam | tolerance | department
    entity_id: str
    action: str               # create | update | delete
    proposed_data: Dict[str, Any]
    original_data: Optional[Dict[str, Any]] = None
    requested_by: str = ""
    requested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"   # pending | approved | rejected
    reviewed_by: str = ""
    reviewed_at: Optional[str] = None
    comment: str = ""


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------

_DETECTORS: Dict[str, Detector] = {}
_LINACS: Dict[str, Linac] = {}
_BEAMS: Dict[str, Beam] = {}
_TOLERANCES: Dict[str, ToleranceTable] = {}
_OUTPUT_RECORDS: Dict[str, OutputRecord] = {}
_PENDING: Dict[str, PendingChange] = {}


# -------------------- Detector --------------------

def add_detector(det: Detector) -> Detector:
    _DETECTORS[det.id] = det
    return det

def get_detector(det_id: str) -> Optional[Detector]:
    return _DETECTORS.get(det_id)

def list_detectors() -> List[Detector]:
    return sorted(_DETECTORS.values(), key=lambda d: d.name.lower())

def update_detector(det_id: str, **kwargs) -> Optional[Detector]:
    det = _DETECTORS.get(det_id)
    if not det:
        return None
    for k, v in kwargs.items():
        if hasattr(det, k):
            setattr(det, k, v)
    return det

def delete_detector(det_id: str) -> bool:
    if det_id in _DETECTORS:
        del _DETECTORS[det_id]
        return True
    return False


# -------------------- Linac --------------------

def add_linac(linac: Linac) -> Linac:
    _LINACS[linac.id] = linac
    return linac

def get_linac(linac_id: str) -> Optional[Linac]:
    return _LINACS.get(linac_id)

def list_linacs() -> List[Linac]:
    return sorted(_LINACS.values(), key=lambda l: l.name.lower())

def update_linac(linac_id: str, **kwargs) -> Optional[Linac]:
    linac = _LINACS.get(linac_id)
    if not linac:
        return None
    for k, v in kwargs.items():
        if hasattr(linac, k):
            setattr(linac, k, v)
    return linac

def delete_linac(linac_id: str) -> bool:
    if linac_id in _LINACS:
        for bid in [b.id for b in _BEAMS.values() if b.linac_id == linac_id]:
            _BEAMS.pop(bid, None)
        del _LINACS[linac_id]
        return True
    return False


# -------------------- Beam --------------------

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

def update_beam(beam_id: str, **kwargs) -> Optional[Beam]:
    beam = _BEAMS.get(beam_id)
    if not beam:
        return None
    for k, v in kwargs.items():
        if hasattr(beam, k):
            setattr(beam, k, v)
    return beam

def delete_beam(beam_id: str) -> bool:
    if beam_id in _BEAMS:
        del _BEAMS[beam_id]
        return True
    return False


# -------------------- Tolerance --------------------

def add_tolerance(tol: ToleranceTable) -> ToleranceTable:
    _TOLERANCES[tol.id] = tol
    return tol

def get_tolerance(tol_id: str) -> Optional[ToleranceTable]:
    return _TOLERANCES.get(tol_id)

def list_tolerances(linac_id: Optional[str] = None, modality: Optional[str] = None) -> List[ToleranceTable]:
    tols = list(_TOLERANCES.values())
    if linac_id is not None:
        tols = [t for t in tols if t.linac_id == linac_id or t.linac_id is None]
    if modality:
        tols = [t for t in tols if t.modality == modality]
    return sorted(tols, key=lambda t: (t.modality, t.name))

def find_tolerance(modality: str, energy: Optional[str] = None, linac_id: Optional[str] = None) -> Optional[ToleranceTable]:
    """Find the most specific matching tolerance."""
    candidates = list_tolerances(linac_id=linac_id, modality=modality)
    # Prefer exact energy match, then energy=None
    for t in candidates:
        if t.energy == energy:
            return t
    for t in candidates:
        if t.energy is None:
            return t
    return None

def update_tolerance(tol_id: str, **kwargs) -> Optional[ToleranceTable]:
    tol = _TOLERANCES.get(tol_id)
    if not tol:
        return None
    for k, v in kwargs.items():
        if hasattr(tol, k):
            setattr(tol, k, v)
    return tol

def delete_tolerance(tol_id: str) -> bool:
    if tol_id in _TOLERANCES:
        del _TOLERANCES[tol_id]
        return True
    return False


def check_tolerance(measured: float, nominal: float, tol: Optional[ToleranceTable]) -> str:
    """Return 'pass' | 'warning' | 'fail' | 'unknown'."""
    if not tol or nominal == 0:
        return "unknown"
    pct = abs(measured - nominal) / nominal * 100.0
    action = tol.action_level_percent if tol.action_level_percent is not None else tol.tolerance_percent * 1.5
    if pct <= tol.tolerance_percent:
        return "pass"
    if pct <= action:
        return "warning"
    return "fail"


# -------------------- Output Record --------------------

def add_output_record(rec: OutputRecord) -> OutputRecord:
    _OUTPUT_RECORDS[rec.id] = rec
    return rec

def list_output_records(linac_id: Optional[str] = None, beam_id: Optional[str] = None) -> List[OutputRecord]:
    recs = list(_OUTPUT_RECORDS.values())
    if linac_id:
        recs = [r for r in recs if r.linac_id == linac_id]
    if beam_id:
        recs = [r for r in recs if r.beam_id == beam_id]
    return sorted(recs, key=lambda r: r.date_time, reverse=True)


# -------------------- Pending Changes (Approval) --------------------

def submit_change(entity_type: str, entity_id: str, action: str,
                  proposed_data: dict, original_data: Optional[dict] = None,
                  requested_by: str = "") -> PendingChange:
    pc = PendingChange(
        id=_new_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        proposed_data=proposed_data,
        original_data=original_data,
        requested_by=requested_by,
    )
    _PENDING[pc.id] = pc
    return pc

def list_pending(status: str = "pending") -> List[PendingChange]:
    return sorted(
        [p for p in _PENDING.values() if p.status == status],
        key=lambda p: p.requested_at, reverse=True,
    )

def get_pending(pc_id: str) -> Optional[PendingChange]:
    return _PENDING.get(pc_id)

def approve_change(pc_id: str, reviewed_by: str = "") -> Optional[PendingChange]:
    pc = _PENDING.get(pc_id)
    if not pc or pc.status != "pending":
        return None
    # Apply the change
    if pc.entity_type == "beam" and pc.action == "update":
        update_beam(pc.entity_id, **pc.proposed_data)
    elif pc.entity_type == "detector" and pc.action == "update":
        update_detector(pc.entity_id, **pc.proposed_data)
    elif pc.entity_type == "linac" and pc.action == "update":
        update_linac(pc.entity_id, **pc.proposed_data)
    elif pc.entity_type == "tolerance" and pc.action == "update":
        update_tolerance(pc.entity_id, **pc.proposed_data)
    elif pc.entity_type == "department" and pc.action == "update":
        update_department(**pc.proposed_data)
    elif pc.entity_type == "beam" and pc.action == "delete":
        delete_beam(pc.entity_id)
    elif pc.entity_type == "detector" and pc.action == "delete":
        delete_detector(pc.entity_id)
    elif pc.entity_type == "tolerance" and pc.action == "delete":
        delete_tolerance(pc.entity_id)

    pc.status = "approved"
    pc.reviewed_by = reviewed_by
    pc.reviewed_at = datetime.utcnow().isoformat()
    return pc

def reject_change(pc_id: str, reviewed_by: str = "", comment: str = "") -> Optional[PendingChange]:
    pc = _PENDING.get(pc_id)
    if not pc or pc.status != "pending":
        return None
    pc.status = "rejected"
    pc.reviewed_by = reviewed_by
    pc.reviewed_at = datetime.utcnow().isoformat()
    pc.comment = comment
    return pc


# -------------------- Seed --------------------

def seed_libraries() -> None:
    if _DETECTORS:
        return

    add_detector(Detector(
        id="det-farmer-01", name="PTW Farmer 30013", detector_type="Cylindrical (Farmer)",
        serial_number="1234", calibration_factor=0.04521, calibration_quality="Co-60",
        calibration_date="2025-03-15", calibration_lab="ADCL Example",
        next_due_date="2027-03-15", notes="Primary photon chamber", unit="Gy/nC",
    ))
    add_detector(Detector(
        id="det-roos-01", name="PTW Roos 34001", detector_type="Parallel-plate",
        serial_number="5678", calibration_factor=0.04815, calibration_quality="Co-60",
        calibration_date="2025-03-15", calibration_lab="ADCL Example",
        next_due_date="2027-03-15", notes="Electron chamber", unit="Gy/nC",
    ))
    add_detector(Detector(
        id="det-well-01", name="SI HDR 1000 Plus", detector_type="Well chamber",
        serial_number="9012", calibration_factor=0.852, calibration_quality="Ir-192",
        calibration_date="2025-01-10", calibration_lab="ADCL Example",
        next_due_date="2026-01-10", notes="HDR well chamber", unit="µGy m² h⁻¹ / nA",
    ))

    add_linac(Linac(id="linac-tb1", name="TrueBeam 1", manufacturer="Varian",
                    model="TrueBeam", serial_number="TB-1001", location="Bunker A"))
    add_linac(Linac(id="linac-hx1", name="Halcyon 1", manufacturer="Varian",
                    model="Halcyon", serial_number="HX-2003", location="Bunker B"))

    add_beam(Beam(id="beam-tb1-6x", linac_id="linac-tb1", modality="photon",
                  nominal_energy="6 MV", measurement_depth_cm=10.0, pdd=0.667, k_Q=0.994, quality_index=0.667))
    add_beam(Beam(id="beam-tb1-10x", linac_id="linac-tb1", modality="photon",
                  nominal_energy="10 MV", measurement_depth_cm=10.0, pdd=0.732, k_Q=0.986, quality_index=0.732))
    add_beam(Beam(id="beam-tb1-15x", linac_id="linac-tb1", modality="photon",
                  nominal_energy="15 MV", measurement_depth_cm=10.0, pdd=0.760, k_Q=0.979))
    add_beam(Beam(id="beam-tb1-6e", linac_id="linac-tb1", modality="electron",
                  nominal_energy="6 MeV", measurement_depth_cm=20.0, pdd=0.05, k_Q=0.920))
    add_beam(Beam(id="beam-tb1-9e", linac_id="linac-tb1", modality="electron",
                  nominal_energy="9 MeV", measurement_depth_cm=20.0, pdd=0.12, k_Q=0.910))
    add_beam(Beam(id="beam-tb1-12e", linac_id="linac-tb1", modality="electron",
                  nominal_energy="12 MeV", measurement_depth_cm=20.0, pdd=0.25, k_Q=0.900))
    add_beam(Beam(id="beam-hx1-6x", linac_id="linac-hx1", modality="photon",
                  nominal_energy="6 MV", measurement_depth_cm=10.0, pdd=0.670, k_Q=0.993))

    add_tolerance(ToleranceTable(
        id="tol-photon-output", name="Photon Output",
        modality="photon", parameter="output", tolerance_percent=2.0, action_level_percent=3.0,
    ))
    add_tolerance(ToleranceTable(
        id="tol-electron-output", name="Electron Output",
        modality="electron", parameter="output", tolerance_percent=2.0, action_level_percent=3.0,
    ))
    add_tolerance(ToleranceTable(
        id="tol-brachy-sk", name="HDR Source Strength",
        modality="brachy", parameter="source_strength", tolerance_percent=3.0,
    ))

    update_department(
        name="Department of Radiation Oncology",
        hospital="Example Cancer Centre",
        city="Your City", country="Your Country",
        head_physicist="Chief Medical Physicist",
    )
