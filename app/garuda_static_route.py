"""Serve Garuda logo at /logo.jpg from app/static/garuda.jpg."""
from pathlib import Path
from fastapi.responses import FileResponse, Response

_STATIC = Path(__file__).resolve().parent / "static"
_LOGO = _STATIC / "garuda.jpg"
_SVG = _STATIC / "garuda.svg"

def ensure_garuda_logo(static_dir=None):
    return _LOGO

def register_garuda_static(app, templates=None):
    @app.get("/logo.jpg")
    async def logo_jpg():
        if _LOGO.exists():
            return FileResponse(
                str(_LOGO),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800"},
            )
        if _SVG.exists():
            return Response(content=_SVG.read_text(), media_type="image/svg+xml")
        return Response(status_code=404)

    # Also keep /static/garuda.jpg working when StaticFiles path is correct
    @app.get("/static/garuda.jpg")
    async def garuda_jpg():
        if _LOGO.exists():
            return FileResponse(
                str(_LOGO),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800"},
            )
        if _SVG.exists():
            return Response(content=_SVG.read_text(), media_type="image/svg+xml")
        return Response(status_code=404)
    return True
