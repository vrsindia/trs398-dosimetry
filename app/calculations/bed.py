"""Loader: reconstruct bed calculations from zlib+b64 parts."""
from __future__ import annotations
import base64, zlib, sys, types
from pathlib import Path

_DIR = Path(__file__).resolve().parent

def _load():
    parts = []
    for i in range(8):
        p = _DIR / f"_bed_p{i}.txt"
        if not p.exists():
            break
        parts.append(p.read_text().strip())
    if not parts:
        raise ImportError("bed parts missing: expected _bed_pN.txt next to bed.py")
    raw = zlib.decompress(base64.b64decode("".join(parts)))
    g = {"__name__": "app.calculations.bed", "__file__": str(_DIR / "bed_impl.py")}
    exec(compile(raw, str(_DIR / "bed_impl.py"), "exec"), g)
    for k, v in list(g.items()):
        if k not in ("__name__", "__file__", "__builtins__"):
            globals()[k] = v
    return g

_load()
