"""Serve Garuda logo from embedded user artwork."""
import base64
from fastapi.responses import Response

_GARUDA = base64.b64decode(
    open(__file__.replace("garuda_static_route.py", "garuda_logo_b64.txt"), encoding="utf-8").read()
    if False
    else """PLACEHOLDER"""
)

def register_garuda_static(app, templates=None):
    @app.get("/static/garuda.jpg")
    async def garuda_jpg():
        return Response(
            content=_GARUDA,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return True
