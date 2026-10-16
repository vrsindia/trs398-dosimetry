"""Embedded Garuda app logo (user-provided artwork, optimized)."""
import base64
from pathlib import Path

# Placeholder - replaced below by full push
def ensure_garuda_logo(static_dir=None):
    static = Path(static_dir) if static_dir else Path(__file__).resolve().parent / "static"
    static.mkdir(parents=True, exist_ok=True)
    target = static / "garuda.jpg"
    return target
