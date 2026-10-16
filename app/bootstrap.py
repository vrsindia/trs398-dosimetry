"""Application entrypoint for Render.

startCommand: uvicorn app.bootstrap:app --host 0.0.0.0 --port $PORT
"""
import traceback

try:
    from app.garuda_static_route import ensure_garuda_logo
    ensure_garuda_logo()
except Exception as e:
    print("garuda_logo:", e)
    traceback.print_exc()

from app.main import app, templates

# Logo routes
try:
    from app.garuda_static_route import register_garuda_static
    register_garuda_static(app, templates)
except Exception as e:
    print("garuda_static:", e)
    traceback.print_exc()

# Core extras
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
        traceback.print_exc()

# Utilities MUST be last so /activity, /bed, /bed-combined are registered
try:
    from app.utility_routes import register_utility_routes
    register_utility_routes(app, templates)
    print("utility_routes OK")
except Exception as e:
    print("utility_routes FAILED:", e)
    traceback.print_exc()

# Patch /health to report utility routes
try:
    from app.health_info import health_payload

    @app.get("/health")
    async def health_with_utils():
        return health_payload(app)
    print("health patched OK")
except Exception as e:
    print("health patch:", e)
    traceback.print_exc()
