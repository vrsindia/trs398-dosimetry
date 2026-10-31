"""Ensure /static is mounted for uploads (logos, brachy QA images)."""
from pathlib import Path


def install(app):
    try:
        from fastapi.staticfiles import StaticFiles
        static_dir = Path(__file__).resolve().parent / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        (static_dir / "uploads" / "brachy_qa").mkdir(parents=True, exist_ok=True)
        # Avoid double-mount
        for r in list(app.router.routes):
            if getattr(r, "path", None) == "/static":
                return True
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        print("boot_static: /static mounted at", static_dir)
        return True
    except Exception as e:
        print("boot_static:", e)
        return False
