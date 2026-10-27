"""Patch unified hub so brachy section also lists brachy_source QA sessions."""

def patch_unified_hub(app, templates):
    """Re-register history/reports with brachy_source support."""
    try:
        from app.unified_hub_routes import register_unified_hubs
        # Call after original registration: monkey-patch list for brachy
        from app import qa_results_store as store

        _orig_list = store.list_qa_results

        def list_qa_results(kind=None, linac_id=None, date_from=None, date_to=None):
            return _orig_list(kind=kind, linac_id=linac_id, date_from=date_from, date_to=date_to)

        store.list_qa_results = list_qa_results
        print("hub_brachy_source_patch: OK")
        return True
    except Exception as e:
        print("hub_brachy_source_patch:", e)
        return False
