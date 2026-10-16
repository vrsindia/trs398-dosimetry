"""Embedded Garuda app logo (user-provided artwork)."""
import base64
from pathlib import Path
from app.garuda_part_a import PART_A
from app.garuda_part_b import PART_B

_GARUDA_JPG_B64 = PART_A + PART_B

def ensure_garuda_logo(static_dir=None):
    static = Path(static_dir) if static_dir else Path(__file__).resolve().parent / "static"
    static.mkdir(parents=True, exist_ok=True)
    target = static / "garuda.jpg"
    raw = base64.b64decode(_GARUDA_JPG_B64)
    if (not target.exists()) or target.stat().st_size != len(raw):
        target.write_bytes(raw)
    return target
