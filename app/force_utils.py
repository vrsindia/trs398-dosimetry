"""Loader: reconstruct force_utils from zlib+b64 parts and register routes."""
from __future__ import annotations
import base64, zlib, sys, types
from pathlib import Path

_DIR = Path(__file__).resolve().parent

def _load():
    parts = []
    for i in range(8):
        p = _DIR / f"_fu_p{i}.txt"
        if not p.exists():
            break
        parts.append(p.read_text().strip())
    if not parts:
        # fallback minimal stub
        def register_force_utils(app, templates=None):
            @app.get("/utils-ping")
            def _ping():
                return {"ok": False, "error": "force_utils parts missing"}
            return app
        return register_force_utils
    raw = zlib.decompress(base64.b64decode("".join(parts)))
    mod = types.ModuleType("app.force_utils_impl")
    mod.__file__ = str(_DIR / "force_utils_impl.py")
    exec(compile(raw, str(_DIR / "force_utils_impl.py"), "exec"), mod.__dict__)
    sys.modules["app.force_utils_impl"] = mod
    return mod.register_force_utils

register_force_utils = _load()
