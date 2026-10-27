"""Late registration of machine library routes (wins over core main)."""

def install(app, templates=None):
    try:
        if templates is None:
            from app.main import templates as templates
        from app.linac_add_patch import register_linac_category_routes
        register_linac_category_routes(app, templates)
        print("boot_machines: linac routes re-registered last")
        return True
    except Exception as e:
        print("boot_machines:", e)
        return False
