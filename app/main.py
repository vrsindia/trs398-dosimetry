"""DOSE pro entry — re-exports app from core_app."""
from app.core_app import app, templates

# Ensure utilities registered
try:
    from app.force_utils import register_force_utils
    register_force_utils(app, templates)
except Exception as e:
    print("force_utils:", e)
