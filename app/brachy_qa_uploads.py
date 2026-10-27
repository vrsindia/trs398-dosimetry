"""Save uploaded images for brachy QA survey / leakage."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

_UPLOAD_DIRS = [
    Path(__file__).resolve().parent / "static" / "uploads" / "brachy_qa",
    Path("/tmp/dosepro/uploads/brachy_qa"),
]


def _dir() -> Path:
    for d in _UPLOAD_DIRS:
        try:
            d.mkdir(parents=True, exist_ok=True)
            t = d / ".w"
            t.write_text("ok")
            t.unlink()
            return d
        except Exception:
            continue
    d = Path("/tmp")
    d.mkdir(exist_ok=True)
    return d


def save_upload(file_obj, prefix: str = "img") -> Optional[str]:
    """Save UploadFile-like object; return relative URL path or None."""
    if file_obj is None:
        return None
    filename = getattr(file_obj, "filename", None) or ""
    if not filename:
        return None
    ext = Path(filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"):
        ext = ".jpg"
    name = "%s_%s%s" % (prefix, uuid.uuid4().hex[:12], ext)
    dest = _dir() / name
    try:
        data = file_obj.file.read()
        if not data:
            return None
        dest.write_bytes(data)
        # Prefer static URL if under app/static
        static_root = Path(__file__).resolve().parent / "static"
        try:
            rel = dest.relative_to(static_root)
            return "/static/" + str(rel).replace("\\", "/")
        except Exception:
            return str(dest)
    except Exception as e:
        print("brachy_qa_uploads:", e)
        return None
