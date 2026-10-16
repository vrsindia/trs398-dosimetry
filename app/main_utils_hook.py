"""Called at end of main.py load to guarantee utility routes exist."""

def hook(app, templates):
    try:
        from app.utility_routes import register_utility_routes
        register_utility_routes(app, templates)
        print("main_utils_hook: utility_routes OK")
    except Exception as e:
        print("main_utils_hook FAILED:", e)
        import traceback
        traceback.print_exc()
