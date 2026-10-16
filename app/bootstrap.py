"""Application entrypoint for Render."""
from app.main import app, templates

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
