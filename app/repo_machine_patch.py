"""Patch repo.save_machine / list_machines to include category."""

def install():
    try:
        import app.repo as repo
        from app.models import Linac, add_linac
        from app.db import use_db, sb_select, sb_upsert

        def list_machines():
            if not use_db():
                from app.models import list_linacs
                return list_linacs()
            rows = sb_select("machines", order="name") or []
            out = []
            for r in rows:
                kwargs = dict(
                    id=r["id"], name=r["name"], manufacturer=r.get("manufacturer") or "",
                    model=r.get("model") or "", serial_number=r.get("serial_number") or "",
                    location=r.get("location") or "", notes=r.get("notes") or "",
                )
                try:
                    out.append(Linac(**kwargs, category=r.get("category") or "ct_linac"))
                except TypeError:
                    m = Linac(**kwargs)
                    if hasattr(m, "category"):
                        m.category = r.get("category") or "ct_linac"
                    out.append(m)
            return out

        def save_machine(m):
            if not use_db():
                add_linac(m)
                return m
            row = {
                "id": m.id, "name": m.name, "manufacturer": m.manufacturer,
                "model": m.model, "serial_number": m.serial_number,
                "location": m.location, "notes": m.notes,
                "category": getattr(m, "category", None) or "ct_linac",
            }
            try:
                sb_upsert("machines", row)
            except Exception:
                row.pop("category", None)
                sb_upsert("machines", row)
            add_linac(m)
            return m

        repo.list_machines = list_machines
        repo.save_machine = save_machine
        print("repo_machine_patch: OK")
        return True
    except Exception as e:
        print("repo_machine_patch:", e)
        return False
