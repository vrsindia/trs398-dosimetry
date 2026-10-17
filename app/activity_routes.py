"""Legacy hook — department is owned by department_routes.py.
Kept so bootstrap import does not fail. Does not register department routes.
"""
from __future__ import annotations


def register_activity_routes(app, templates):
    # Department edit/save/logo are registered by app.department_routes.
    # Do not override them here.
    return True
