"""Shared health payload including Supabase status and utility routes."""
from app.db import status as db_status


def health_payload(app=None) -> dict:
    try:
        storage = db_status()
    except Exception as e:
        storage = {"mode": "in-memory", "using_database": False, "error": str(e)}

    utility_paths = []
    all_paths = []
    if app is not None:
        try:
            for r in app.router.routes:
                p = getattr(r, "path", None)
                if not p:
                    continue
                all_paths.append(p)
                if p in ("/activity", "/bed", "/bed-combined", "/utils-ping"):
                    utility_paths.append(p)
            utility_paths = sorted(set(utility_paths))
        except Exception as e:
            utility_paths = [f"error: {e}"]

    return {
        "status": "ok",
        "app": "DOSE pro",
        "version": "1.6.0",
        "storage": storage,
        "utility_routes": utility_paths,
        "utility_ok": all(p in utility_paths for p in ("/activity", "/bed", "/bed-combined")),
        "supabase_hint": (
            "Set SUPABASE_URL and SUPABASE_KEY on Render Environment, "
            "then confirm tables exist in Supabase Table Editor."
            if not storage.get("using_database")
            else "Connected to Supabase."
        ),
    }
