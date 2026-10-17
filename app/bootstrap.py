"""Render entrypoint: uvicorn app.bootstrap:app --host 0.0.0.0 --port $PORT"""
import traceback

from app.main import app, templates

try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
    print("force_utils OK")
except Exception as e:
    print("FORCE_UTILS FAILED:", e)
    traceback.print_exc()

for _label, _mod, _fn in [
    ("extra_routes", "app.extra_routes", "register_extra_routes"),
    ("history_routes", "app.history_routes", "register_history_routes"),
    ("storage_hooks", "app.storage_hooks", "register_storage_hooks"),
    ("report_view", "app.report_view_route", "register_report_view"),
    ("linac_category", "app.linac_add_patch", "register_linac_category_routes"),
    ("branding_routes", "app.branding_routes", "register_branding_routes"),
    ("mr_energy_patch", "app.mr_energy_patch", "register_mr_energy_patch"),
    ("activity_routes", "app.activity_routes", "register_activity_routes"),
]:
    try:
        mod = __import__(_mod, fromlist=[_fn])
        getattr(mod, _fn)(app, templates)
        print(_label, "OK")
    except Exception as e:
        print(_label + ":", e)

try:
    import app.force_utils as fu
    if hasattr(fu, "_DONE"):
        fu._DONE = False
    fu.register_force_utils(app, templates)
    print("force_utils re-OK")
except Exception as e:
    print("FORCE_UTILS 2:", e)
    traceback.print_exc()

# Department routes LAST — must win over core main.py /department handlers
try:
    from app.department_routes import register_department_routes
    register_department_routes(app, templates)
    print("department_routes OK")
except Exception as e:
    print("department_routes:", e)
    traceback.print_exc()


@app.on_event("startup")
def _rebind_department():
    """Re-bind department after full startup so no earlier route can shadow it."""
    try:
        from app.department_routes import register_department_routes
        register_department_routes(app, templates)
        print("department_routes startup rebind OK")
    except Exception as e:
        print("department startup rebind failed:", e)
        traceback.print_exc()
