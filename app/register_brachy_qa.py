"""Register brachy source QA from bootstrap / force_utils."""

def install(app, templates=None):
    try:
        if templates is None:
            from app.main import templates as templates
        from app.brachy_qa_routes import register_brachy_qa_routes
        register_brachy_qa_routes(app, templates)
        print("register_brachy_qa: OK")
        return True
    except Exception as e:
        print("register_brachy_qa:", e)
        return False
