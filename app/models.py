"""
Core data models for Detector, Linac and Beam libraries.
In-memory for now (zero-cost). Easy to migrate to Supabase later.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import date, datetime
import uuid


# ---------------------------------------------------------------------------
# Detector Library
# ---------------------------------------------------------------------------

@dataclass
class Detector:
    id: str
    name: str
    detector_type: str                  # Farmer, Parallel-plate, Well, Diode, etc.
    serial_number: str
    calibration_factor: float           # N_D,w (Gy/nC) or N_SK for well chambers
    calibration_quality: str = "Co-60"  # Co-60, Ir-192, etc.
    calibration_date: Optional[str] = None   # ISO date YYYY-MM-DD
    calibration_lab: Optional[str] = None
    next_due_date: Optional[str] = None      # ISO date YYYY-MM-DD
    notes: str = ""
    unit: str = "Gy/nC"                 # or "µGy m² h⁻¹ nA⁻¹" etc.

    def is_overdue(self) -> bool:
        if not self.next_due_date:
            return False
        try:
            due = date.fromisoformat(self.next_due_date)
            return date.today() > due
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Linac Library
# ---------------------------------------------------------------------------

@dataclass
class Linac:
    id: str
    name: str                           # e.g. "TrueBeam 1", "Halcyon A"
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Beam / Energy configuration (per Linac)
# ---------------------------------------------------------------------------

@dataclass
class Beam:
    id: str
    linac_id: str
    modality: str                       # "photon" or "electron"
    nominal_energy: str                 # "6 MV", "10 MV", "9 MeV", etc.
    measurement_depth_cm: float         # 10.0 for photons, 20.0 for electrons (clinic practice)
    pdd: float                          # PDD at the measurement depth (fraction, e.g. 0.67)
    k_Q: float                          # k_Q or k_Q,Q0
    ssd_cm: float = 100.0
    field_size: str = "10x10"
    notes: str = ""


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_DETECTORS: Dict[str, Detector] = {}
_LINACS: Dict[str, Linac] = {}
_BEAMS: Dict[str, Beam] = {}


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


# -------------------- Detector CRUD --------------------

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
        if hasattr(det, k) and v is not None:
            setattr(det, k, v)
    return det

def delete_detector(det_id: str) -> bool:
    if det_id in _DETECTORS:
        del _DETECTORS[det_id]
        return True
    return False


# -------------------- Linac CRUD --------------------

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
        if hasattr(linac, k) and v is not None:
            setattr(linac, k, v)
    return linac

def delete_linac(linac_id: str) -> bool:
    if linac_id in _LINACS:
        # also remove associated beams
        to_delete = [b.id for b in _BEAMS.values() if b.linac_id == linac_id]
        for bid in to_delete:
            del _BEAMS[bid]
        del _LINACS[linac_id]
        return True
    return False


# -------------------- Beam CRUD --------------------

def add_beam(beam: Beam) -> Beam:
    _BEAMS[beam.id] = beam
    return beam

def get_beam(beam_id: str) -> Optional[Beam]:
    return _BEAMS.get(beam_id)

def list_beams(linac_id: Optional[str] = None) -> List[Beam]:
    beams = list(_BEAMS.values())
    if linac_id:
        beams = [b for b in beams if b.linac_id == linac_id]
    return sorted(beams, key=lambda b: (b.modality, b.nominal_energy))

def update_beam(beam_id: str, **kwargs) -> Optional[Beam]:
    beam = _BEAMS.get(beam_id)
    if not beam:
        return None
    for k, v in kwargs.items():
        if hasattr(beam, k) and v is not None:
            setattr(beam, k, v)
    return beam

def delete_beam(beam_id: str) -> bool:
    if beam_id in _BEAMS:
        del _BEAMS[beam_id]
        return True
    return False


# -------------------- Seed example data --------------------

def seed_libraries() -> None:
    """Populate with realistic example data if empty."""
    if _DETECTORS:
        return

    # Detectors
    add_detector(Detector(
        id="det-farmer-01",
        name="PTW Farmer 30013",
        detector_type="Cylindrical (Farmer)",
        serial_number="1234",
        calibration_factor=0.04521,
        calibration_quality="Co-60",
        calibration_date="2025-03-15",
        calibration_lab="ADCL Example Lab",
        next_due_date="2027-03-15",
        notes="Primary photon chamber",
        unit="Gy/nC",
    ))
    add_detector(Detector(
        id="det-roos-01",
        name="PTW Roos 34001",
        detector_type="Parallel-plate",
        serial_number="5678",
        calibration_factor=0.04815,
        calibration_quality="Co-60",
        calibration_date="2025-03-15",
        calibration_lab="ADCL Example Lab",
        next_due_date="2027-03-15",
        notes="Electron chamber",
        unit="Gy/nC",
    ))
    add_detector(Detector(
        id="det-well-01",
        name="SI HDR 1000 Plus",
        detector_type="Well chamber",
        serial_number="9012",
        calibration_factor=0.852,
        calibration_quality="Ir-192",
        calibration_date="2025-01-10",
        calibration_lab="ADCL Example Lab",
        next_due_date="2026-01-10",
        notes="HDR well chamber",
        unit="µGy m² h⁻¹ / nA",
    ))

    # Linacs
    add_linac(Linac(
        id="linac-tb1",
        name="TrueBeam 1",
        manufacturer="Varian",
        model="TrueBeam",
        serial_number="TB-1001",
        location="Bunker A",
    ))
    add_linac(Linac(
        id="linac-hx1",
        name="Halcyon 1",
        manufacturer="Varian",
        model="Halcyon",
        serial_number="HX-2003",
        location="Bunker B",
    ))

    # Beams for TrueBeam 1
    add_beam(Beam(
        id="beam-tb1-6x",
        linac_id="linac-tb1",
        modality="photon",
        nominal_energy="6 MV",
        measurement_depth_cm=10.0,
        pdd=0.667,
        k_Q=0.994,
        notes="TPR20,10 based k_Q",
    ))
    add_beam(Beam(
        id="beam-tb1-10x",
        linac_id="linac-tb1",
        modality="photon",
        nominal_energy="10 MV",
        measurement_depth_cm=10.0,
        pdd=0.732,
        k_Q=0.986,
    ))
    add_beam(Beam(
        id="beam-tb1-15x",
        linac_id="linac-tb1",
        modality="photon",
        nominal_energy="15 MV",
        measurement_depth_cm=10.0,
        pdd=0.760,
        k_Q=0.979,
    ))
    add_beam(Beam(
        id="beam-tb1-6e",
        linac_id="linac-tb1",
        modality="electron",
        nominal_energy="6 MeV",
        measurement_depth_cm=20.0,   # clinic practice as specified
        pdd=0.05,                   # illustrative
        k_Q=0.920,
    ))
    add_beam(Beam(
        id="beam-tb1-9e",
        linac_id="linac-tb1",
        modality="electron",
        nominal_energy="9 MeV",
        measurement_depth_cm=20.0,
        pdd=0.12,
        k_Q=0.910,
    ))
    add_beam(Beam(
        id="beam-tb1-12e",
        linac_id="linac-tb1",
        modality="electron",
        nominal_energy="12 MeV",
        measurement_depth_cm=20.0,
        pdd=0.25,
        k_Q=0.900,
    ))

    # Beams for Halcyon
    add_beam(Beam(
        id="beam-hx1-6x",
        linac_id="linac-hx1",
        modality="photon",
        nominal_energy="6 MV",
        measurement_depth_cm=10.0,
        pdd=0.670,
        k_Q=0.993,
    ))
