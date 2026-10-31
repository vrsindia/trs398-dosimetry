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
            _install_extras(app, templates)
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
        _install_extras(app, templates)
        return app

    return register_force_utils


def _install_extras(app, templates=None):
    try:
        from app.boot_static import install as install_static
        install_static(app)
    except Exception as e:
        print("force_utils: boot_static:", e)
    try:
        from app.repo_machine_patch import install as install_repo_m
        install_repo_m()
    except Exception as e:
        print("force_utils: repo_machine_patch:", e)
    try:
        from app.user_sync_routes import register_user_sync_routes
        register_user_sync_routes(app)
        print("force_utils: user_sync_routes OK")
    except Exception as e:
        print("force_utils: user_sync_routes failed:", e)
    try:
        from app.main import templates as tpl
        templates = templates or tpl
        from app.users_routes import register_users_routes
        register_users_routes(app, templates)
        print("force_utils: users_routes re-registered")
    except Exception as e:
        print("force_utils: users_routes:", e)
    try:
        from app.register_brachy_qa import install as install_brachy_qa
        install_brachy_qa(app, templates)
    except Exception as e:
        print("force_utils: brachy_qa:", e)
    try:
        from app.main import templates as tpl
        templates = templates or tpl
        from app.tolerances_routes import register_tolerances_routes
        register_tolerances_routes(app, templates)
        print("force_utils: tolerances_routes OK")
    except Exception as e:
        print("force_utils: tolerances_routes:", e)
    try:
        from app.boot_machines import install as install_machines
        install_machines(app, templates)
    except Exception as e:
        print("force_utils: boot_machines:", e)


register_force_utils = _load()
