"""Application entrypoint for Render."""
try:
    from app.garuda_static_route import ensure_garuda_logo, register_garuda_static
    ensure_garuda_logo()
except Exception as e:
    print("garuda_logo:", e)

from app.main import app, templates

try:
    from app.garuda_static_route import register_garuda_static
    register_garuda_static(app, templates)
except Exception as e:
    print("garuda_static:", e)

try:
    from app.extra_routes import register_extra_routes
    register_extra_routes(app, templates)
except Exception as e:
    print("extra_routes:", e)

try:
    from app.history_routes import register_history_routes
    register_history_routes(app, templates)
except Exception as e:
    print("history_routes:", e)

try:
    from app.storage_hooks import register_storage_hooks
    register_storage_hooks(app, templates)
except Exception as e:
    print("storage_hooks:", e)

try:
    from app.report_view_route import register_report_view
    register_report_view(app, templates)
except Exception as e:
    print("report_view:", e)

try:
    from app.linac_add_patch import register_linac_category_routes
    register_linac_category_routes(app, templates)
except Exception as e:
    print("linac_category:", e)

try:
    from app.branding_routes import register_branding_routes
    register_branding_routes(app, templates)
except Exception as e:
    print("branding_routes:", e)

try:
    from app.mr_energy_patch import register_mr_energy_patch
    register_mr_energy_patch(app, templates)
except Exception as e:
    print("mr_energy_patch:", e)

# Utilities last so they override any prior /activity routes
try:
    from app.utility_routes import register_utility_routes
    register_utility_routes(app, templates)
except Exception as e:
    print("utility_routes:", e)

try:
    from app.activity_routes import register_activity_routes
    # Keep department admin routes from activity_routes; utility owns /activity
    register_activity_routes(app, templates)
except Exception as e:
    print("activity_routes:", e)

# Re-apply utility activity routes after activity_routes (so /activity stays hardened)
try:
    from app.utility_routes import register_utility_routes
    register_utility_routes(app, templates)
except Exception as e:
    print("utility_routes_2:", e)
