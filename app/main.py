"""DOSE pro — load core from known-good commit, then register utilities."""
import urllib.request
from pathlib import Path

# Known-good main.py from commit before PLACEHOLDER corruption
_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "fbac98317ebcbd9c31bd85ec7815df834ceac023/app/main.py"
)

try:
    _code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
    exec(compile(_code, "app/main.py", "exec"), globals())
except Exception as _e:
    # Offline / fallback: try local core_app parts if present
    print("history load failed:", _e)
    _p = Path(__file__).resolve().parent
    _parts = [_p / f"_mp{i}.txt" for i in range(4)]
    if all(x.exists() for x in _parts):
        _code = "".join(x.read_text() for x in _parts)
        exec(compile(_code, str(_p / "core_app.py"), "exec"), globals())
    else:
        raise RuntimeError(f"Cannot load application: {_e}") from _e

# Register utility routes (activity, BED, EQD2, EBRT+Brachy)
try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
except Exception as e:
    print("force_utils:", e)
