"""Side-effect import: registers extra routes when loaded."""

def activate(app, templates):
    from app.extra_routes import register_extra_routes
    register_extra_routes(app, templates)
