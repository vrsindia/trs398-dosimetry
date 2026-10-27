"""Brachy source QA tolerances — sourced from tolerance library (non-editable in QA UI)."""
from __future__ import annotations

from typing import Optional

# parameter key -> default (name, tolerance_percent, notes)
BRACHY_QA_TOLS = {
    "brachy_timer_error": ("Brachy timer error", 1.0, "% timer error vs dwell time"),
    "brachy_timer_linearity": ("Brachy timer linearity", 1.0, "Max residual % of linear fit"),
    "brachy_decay": ("Brachy decay factor", 1.0, "% deviation manual vs TPS"),
    "brachy_tps_single": ("Brachy single source vs TPS", 3.0, "% treatment time deviation"),
    "brachy_tps_multi": ("Brachy multi source vs TPS", 3.0, "% treatment time deviation"),
    "brachy_position": ("Brachy positioning accuracy", 1.0, "mm (use as absolute limit)"),
    "brachy_contamination": ("Brachy contamination", 200.0, "Bq limit"),
}


def ensure_brachy_tolerances() -> None:
    """Seed missing brachy QA tolerances into the library (idempotent)."""
    try:
        from app.models import ToleranceTable, add_tolerance, list_tolerances, _new_id
    except Exception:
        try:
            from app.models import ToleranceTable, add_tolerance, list_tolerances
            def _new_id():
                import uuid
                return uuid.uuid4().hex[:12]
        except Exception as e:
            print("ensure_brachy_tolerances import:", e)
            return

    existing = {getattr(t, "parameter", "") for t in (list_tolerances() or [])}
    for param, (name, tol_pct, notes) in BRACHY_QA_TOLS.items():
        if param in existing:
            continue
        try:
            add_tolerance(ToleranceTable(
                id="tol-" + param.replace("_", "-")[:20],
                name=name,
                modality="brachy",
                parameter=param,
                tolerance_percent=float(tol_pct),
                action_level_percent=float(tol_pct),
                notes=notes,
            ))
        except Exception as e:
            print("seed tol", param, e)


def get_brachy_tol(parameter: str) -> dict:
    """Return {percent, name, notes, source} from library or built-in default."""
    ensure_brachy_tolerances()
    default_name, default_pct, default_notes = BRACHY_QA_TOLS.get(
        parameter, (parameter, 1.0, "")
    )
    try:
        from app.models import list_tolerances
        for t in list_tolerances() or []:
            if getattr(t, "parameter", "") == parameter:
                return {
                    "percent": float(getattr(t, "tolerance_percent", default_pct) or default_pct),
                    "name": getattr(t, "name", default_name) or default_name,
                    "notes": getattr(t, "notes", "") or default_notes,
                    "source": "tolerance library",
                }
    except Exception as e:
        print("get_brachy_tol:", e)
    return {
        "percent": float(default_pct),
        "name": default_name,
        "notes": default_notes,
        "source": "default",
    }
