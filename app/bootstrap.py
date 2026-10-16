"""
Application entrypoint for Render.
"""
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
