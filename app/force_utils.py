"""Loader: reconstruct force_utils from zlib+b64 parts and register routes."""
from __future__ import annotations
import base64, zlib, sys, types
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load():
    parts = []
    for i in range(8):
        p = _DIR / ("_fu_p%d.txt" % i)
        if not p.exists():
            break
        parts.append(p.read_text().strip())
    if not parts:
        def register_force_utils(app, templates=None):
            @app.get("/utils-ping")
            def _ping():
                return {"ok": False, "error": "force_utils parts missing"}
            _install_user_sync(app)
            return app
        return register_force_utils
    raw = zlib.decompress(base64.b64decode("".join(parts)))
    mod = types.ModuleType("app.force_utils_impl")
    mod.__file__ = str(_DIR / "force_utils_impl.py")
    exec(compile(raw, str(_DIR / "force_utils_impl.py"), "exec"), mod.__dict__)
    sys.modules["app.force_utils_impl"] = mod
    _orig = mod.register_force_utils

    def register_force_utils(app, templates=None):
        try:
            _orig(app, templates)
        except TypeError:
            _orig(app)
        _install_user_sync(app)
        return app

    return register_force_utils


def _install_user_sync(app):
    try:
        from app.user_sync_routes import register_user_sync_routes
        register_user_sync_routes(app)
        print("force_utils: user_sync_routes OK")
    except Exception as e:
        print("force_utils: user_sync_routes failed:", e)
    try:
        from app.users_routes import register_users_routes
        # templates may be missing; only if already on app
        templates = getattr(app, "state", None)
        from app.main import templates as tpl
        register_users_routes(app, tpl)
        print("force_utils: users_routes re-registered")
    except Exception as e:
        print("force_utils: users_routes:", e)


register_force_utils = _load()
