"""Serve Garuda logo from app/static/garuda.jpg (repo file)."""
from pathlib import Path
from fastapi.responses import FileResponse, Response

_STATIC = Path(__file__).resolve().parent / "static"
_LOGO = _STATIC / "garuda.jpg"

def ensure_garuda_logo(static_dir=None):
    return _LOGO

def register_garuda_static(app, templates=None):
    @app.get("/static/garuda.jpg")
    async def garuda_jpg():
        if _LOGO.exists():
            return FileResponse(
                str(_LOGO),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800"},
            )
        # SVG fallback if jpg missing
        svg_path = _STATIC / "garuda.svg"
        if svg_path.exists():
            return Response(content=svg_path.read_text(), media_type="image/svg+xml")
        return Response(status_code=404)
    return True
