"""Render entrypoint: uvicorn app.bootstrap:app --host 0.0.0.0 --port $PORT"""
import traceback

from app.main import app, templates

try:
    from app.auth_supabase import hydrate_users_from_supabase, patch_auth_for_supabase
    n = hydrate_users_from_supabase()
    if n:
        print("Loaded %d users from Supabase" % n)
    else:
        from app.auth import seed_users
        seed_users()
        print("seed_users (in-memory defaults)")
    patch_auth_for_supabase()
except Exception as e:
    print("auth_supabase:", e)
    try:
        from app.auth import seed_users
        seed_users()
    except Exception:
        pass

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
    from app.department_routes import register_department_routes
    register_department_routes(app, templates)
    print("department_routes OK")
except Exception as e:
    print("department_routes:", e)

try:
    from app.fix_utils import register_fix_utils
    register_fix_utils(app, templates)
    print("fix_utils OK")
except Exception as e:
    print("fix_utils FAILED:", e)

try:
    from app.fix_fractionation import register_fix_fractionation
    register_fix_fractionation(app, templates)
except Exception as e:
    print("fix_fractionation:", e)

try:
    from app.fix_oar import register_fix_oar
    register_fix_oar(app, templates)
except Exception as e:
    print("fix_oar:", e)

try:
    from app.fix_calc import register_fix_calc
    register_fix_calc(app, templates)
    print("fix_calc OK")
except Exception as e:
    print("fix_calc FAILED:", e)
    traceback.print_exc()

try:
    from app.users_routes import register_users_routes
    register_users_routes(app, templates)
    print("users_routes OK")
except Exception as e:
    print("users_routes FAILED:", e)
    traceback.print_exc()

try:
    from app.qa_mount import mount_qa
    mount_qa(app, templates)
    print("qa_mount OK")
except Exception as e:
    print("qa_mount FAILED:", e)
    traceback.print_exc()

try:
    from app.qa_history_routes import mount_qa_history
    mount_qa_history(app, templates)
    print("qa_history OK")
except Exception as e:
    print("qa_history FAILED:", e)
    traceback.print_exc()


def _mount_hubs():
    from app.unified_hub_routes import register_unified_hubs
    register_unified_hubs(app, templates)
    hub_paths = {
        "/history", "/output-history", "/qa-history",
        "/reports", "/qa-reports", "/hub-ping",
    }
    hub, rest = [], []
    for r in list(app.router.routes):
        p = getattr(r, "path", None)
        (hub if p in hub_paths else rest).append(r)
    app.router.routes[:] = hub + rest
    print("unified_hubs OK (routes prepended)")


try:
    _mount_hubs()
except Exception as e:
    print("unified_hubs FAILED:", e)
    traceback.print_exc()

# PDF generate — last, dedicated path, no storage
try:
    from app.report_generate import register_report_generate
    register_report_generate(app, templates)
    print("report_generate OK")
except Exception as e:
    print("report_generate FAILED:", e)
    traceback.print_exc()


@app.on_event("startup")
def _startup_rebind():
    try:
        from app.qa_mount import mount_qa
        mount_qa(app, templates)
    except Exception as e:
        print("qa_mount startup:", e)
    try:
        from app.qa_history_routes import mount_qa_history
        mount_qa_history(app, templates)
    except Exception as e:
        print("qa_history startup:", e)
    try:
        _mount_hubs()
        print("unified_hubs startup OK")
    except Exception as e:
        print("unified_hubs startup FAILED:", e)
        traceback.print_exc()
    try:
        from app.report_generate import register_report_generate
        register_report_generate(app, templates)
        print("report_generate startup OK")
    except Exception as e:
        print("report_generate startup:", e)
        traceback.print_exc()
