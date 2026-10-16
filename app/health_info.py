"""Shared health payload including Supabase status."""
from app.db import status as db_status


def health_payload() -> dict:
    try:
        storage = db_status()
    except Exception as e:
        storage = {"mode": "in-memory", "using_database": False, "error": str(e)}
    return {
        "status": "ok",
        "app": "DOSE pro",
        "version": "1.5.0",
        "storage": storage,
        "supabase_hint": (
            "Set SUPABASE_URL and SUPABASE_KEY on Render Environment, "
            "then confirm tables exist in Supabase Table Editor."
            if not storage.get("using_database")
            else "Connected to Supabase."
        ),
    }
