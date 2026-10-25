"""Import side-effect: register user sync routes on whatever app is current."""

def install(app):
    try:
        from app.user_sync_routes import register_user_sync_routes
        register_user_sync_routes(app)
        print("force_user_sync: OK")
        return True
    except Exception as e:
        print("force_user_sync:", e)
        return False
