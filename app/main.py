"""DOSE pro — load core from known-good commit, then register utilities + hubs."""
import urllib.request
from pathlib import Path

_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "fbac98317ebcbd9c31bd85ec7815df834ceac023/app/main.py"
)

try:
    _code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
    exec(compile(_code, "app/main.py", "exec"), globals())
except Exception as _e:
    print("history load failed:", _e)
    _p = Path(__file__).resolve().parent
    _parts = [_p / ("_mp%d.txt" % i) for i in range(4)]
    if all(x.exists() for x in _parts):
        _code = "".join(x.read_text() for x in _parts)
        exec(compile(_code, str(_p / "core_app.py"), "exec"), globals())
    else:
        raise RuntimeError("Cannot load application: %s" % _e) from _e

try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
except Exception as e:
    print("force_utils:", e)

try:
    from app.qa_mount import mount_qa
    mount_qa(app, templates)
    print("main: qa_mount OK")
except Exception as e:
    print("main: qa_mount:", e)

try:
    from app.unified_hub_routes import register_unified_hubs
    register_unified_hubs(app, templates)
    print("main: unified_hubs OK")
except Exception as e:
    print("main: unified_hubs:", e)
