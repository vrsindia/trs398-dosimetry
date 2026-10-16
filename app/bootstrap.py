"""
Application entrypoint used by Render.
Loads main app then registers extra routes (calc profiles, reports, energy UX).
"""
from app.main import app, templates

from app.extra_routes import register_extra_routes
register_extra_routes(app, templates)

# app is the FastAPI instance exported for uvicorn app.bootstrap:app
