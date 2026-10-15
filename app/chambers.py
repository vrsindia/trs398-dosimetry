"""
Simple in-memory chamber and certificate registry.
For a single-physicist tool this is sufficient and keeps the app zero-cost.
Later this can be replaced by Supabase or another database.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import date


@dataclass
class Chamber:
    id: str
    name: str
    type: str                          # Farmer, parallel-plate, well, etc.
    serial_number: str
    N_Dw: float                        # Gy/nC or appropriate unit
    calibration_quality: str = "Co-60"
    calibration_date: Optional[str] = None
    calibration_lab: Optional[str] = None
    notes: str = ""


# In-memory store (resets on every cold start – acceptable for single-user free tier)
_CHAMBERS: Dict[str, Chamber] = {}


def add_chamber(chamber: Chamber) -> None:
    _CHAMBERS[chamber.id] = chamber


def get_chamber(chamber_id: str) -> Optional[Chamber]:
    return _CHAMBERS.get(chamber_id)


def list_chambers() -> List[Chamber]:
    return list(_CHAMBERS.values())


def delete_chamber(chamber_id: str) -> bool:
    if chamber_id in _CHAMBERS:
        del _CHAMBERS[chamber_id]
        return True
    return False


def seed_example_chambers() -> None:
    """Add a couple of example chambers for demonstration."""
    if _CHAMBERS:
        return
    add_chamber(Chamber(
        id="farmer-001",
        name="PTW Farmer 30013",
        type="Cylindrical (Farmer)",
        serial_number="1234",
        N_Dw=0.0452,
        calibration_quality="Co-60",
        calibration_date="2025-03-15",
        calibration_lab="ADCL Example",
        notes="Primary photon chamber",
    ))
    add_chamber(Chamber(
        id="ppc-001",
        name="PTW Roos 34001",
        type="Parallel-plate",
        serial_number="5678",
        N_Dw=0.0481,
        calibration_quality="Co-60",
        calibration_date="2025-03-15",
        calibration_lab="ADCL Example",
        notes="Electron chamber",
    ))
    add_chamber(Chamber(
        id="well-001",
        name="Standard Imaging HDR 1000 Plus",
        type="Well chamber",
        serial_number="9012",
        N_Dw=0.0,               # well chambers use N_SK instead
        calibration_quality="Ir-192",
        calibration_date="2025-01-10",
        calibration_lab="ADCL Example",
        notes="HDR well chamber – use N_SK field in brachy module",
    ))
