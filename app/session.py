"""
Simple in-memory session store for a guided absolute dosimetry session.
Holds shared correction factors so they can be reused across energies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime
import uuid


@dataclass
class SessionCorrectionFactors:
    k_TP: float = 1.0
    k_pol: float = 1.0
    k_s: float = 1.0
    temperature_C: float = 20.0
    pressure_hPa: float = 1013.25
    calculated: bool = False


@dataclass
class DosimetrySession:
    id: str
    linac_id: str
    modality: str                          # photon | electron
    detector_id: Optional[str] = None
    corrections: SessionCorrectionFactors = field(default_factory=SessionCorrectionFactors)
    quality_index: Optional[float] = None  # TPR20,10 for photons
    completed_energies: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


_SESSIONS: Dict[str, DosimetrySession] = {}


def create_session(linac_id: str, modality: str) -> DosimetrySession:
    sid = str(uuid.uuid4())[:8]
    sess = DosimetrySession(id=sid, linac_id=linac_id, modality=modality)
    _SESSIONS[sid] = sess
    return sess


def get_session(session_id: str) -> Optional[DosimetrySession]:
    return _SESSIONS.get(session_id)


def update_session(session_id: str, **kwargs) -> Optional[DosimetrySession]:
    sess = _SESSIONS.get(session_id)
    if not sess:
        return None
    for k, v in kwargs.items():
        if hasattr(sess, k):
            setattr(sess, k, v)
    return sess
