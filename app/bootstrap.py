"""
Application entrypoint used by Render.
Loads main app then registers extra routes.
"""
from app.main import app, templates

try:
    from app.extra_routes import register_extra_routes
    register_extra_routes(app, templates)
except Exception as e:
    print("extra_routes failed:", e)

try:
    from app.history_routes import register_history_routes
    register_history_routes(app, templates)
except Exception as e:
    print("history_routes failed:", e)
