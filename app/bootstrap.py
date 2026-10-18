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

# Unified History + Reports hubs (override list pages, keep PDF endpoints)
try:
    from app.unified_hub_routes import register_unified_hubs
    register_unified_hubs(app, templates)
    print("unified_hubs OK")
except Exception as e:
    print("unified_hubs FAILED:", e)
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
        from app.unified_hub_routes import register_unified_hubs
        register_unified_hubs(app, templates)
        print("unified_hubs startup OK")
    except Exception as e:
        print("unified_hubs startup:", e)
    for label, mod_name, fn_name in [
        ("department", "app.department_routes", "register_department_routes"),
        ("users_routes", "app.users_routes", "register_users_routes"),
    ]:
        try:
            mod = __import__(mod_name, fromlist=[fn_name])
            getattr(mod, fn_name)(app, templates)
        except Exception as e:
            print(label, "startup:", e)
    try:
        from app.qa_mount import mount_qa
        mount_qa(app, templates)
        from app.qa_history_routes import mount_qa_history
        mount_qa_history(app, templates)
        from app.unified_hub_routes import register_unified_hubs
        register_unified_hubs(app, templates)
        print("hubs final startup OK")
    except Exception as e:
        print("hubs final startup:", e)
