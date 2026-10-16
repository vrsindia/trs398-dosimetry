"""Serve user Garuda logo."""
import base64
from pathlib import Path
from fastapi.responses import Response
from app.logo_p0 import P0
from app.logo_p1 import P1
from app.logo_p2 import P2

_BYTES = base64.b64decode(P0 + P1 + P2)

def ensure_file():
    p = Path(__file__).resolve().parent / "static" / "garuda.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.stat().st_size != len(_BYTES):
        p.write_bytes(_BYTES)
    return p

def register_garuda_static(app, templates=None):
    ensure_file()
    @app.get("/static/garuda.jpg")
    async def garuda_jpg():
        return Response(
            content=_BYTES,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )
    return True
