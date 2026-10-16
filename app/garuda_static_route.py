"""Serve Garuda logo: prefer static/garuda.jpg file, else assemble from g*.txt parts."""
from pathlib import Path
import base64
from fastapi.responses import Response, FileResponse

_STATIC = Path(__file__).resolve().parent / "static"
_CACHE = None

def _load_bytes():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    jpg = _STATIC / "garuda.jpg"
    if jpg.exists() and jpg.stat().st_size > 100:
        _CACHE = jpg.read_bytes()
        return _CACHE
    parts = []
    for i in range(20):
        f = _STATIC / f"g{i}.txt"
        if not f.exists():
            break
        parts.append(f.read_text().strip())
    if parts:
        _CACHE = base64.b64decode("".join(parts))
        # also write garuda.jpg for StaticFiles
        try:
            jpg.write_bytes(_CACHE)
        except Exception:
            pass
        return _CACHE
    # minimal 1x1 jpeg fallback
    _CACHE = base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="
    )
    return _CACHE

def register_garuda_static(app, templates=None):
    @app.get("/static/garuda.jpg")
    async def garuda_jpg():
        data = _load_bytes()
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )
    return True
