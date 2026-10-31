"""Register POST /brachy-source-qa/save-last using cached calculation."""
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.auth import get_user_by_token
from app import brachy_qa_cache as cache

COOKIE = "dosepro_session"


def register_brachy_save_last(app, templates):
    @app.post("/brachy-source-qa/save-last")
    async def save_last(request: Request):
        user = get_user_by_token(request.cookies.get(COOKIE))
        if not user:
            return RedirectResponse("/login", 303)
        form = await request.form()
        section = str(form.get("section") or "")
        uname = getattr(user, "username", "") or ""
        payload = cache.get(uname, section)
        if not payload:
            return RedirectResponse(
                "/brachy-source-qa?section=%s&msg=Nothing+to+save+-+Calculate+first" % section,
                303,
            )
        if not payload.get("pass"):
            return RedirectResponse(
                "/brachy-source-qa?section=%s&msg=Cannot+save+-+outside+tolerance" % section,
                303,
            )
        try:
            from app.qa_results_store import save_qa_result
            rows = payload.get("rows") or []
            results = []
            for item in rows:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    results.append({"parameter": str(item[0]), "value": str(item[1])})
                elif isinstance(item, dict):
                    results.append(item)
            row = save_qa_result(
                kind="brachy_source",
                linac_id="brachy",
                linac_name="Brachy source",
                overall=payload.get("overall") or "Satisfactory",
                results=results,
                performed_by=uname,
                notes=payload.get("formula") or "",
            )
            row["title"] = payload.get("title") or section
            row["annexure"] = payload.get("annexure") or section
            row["formula"] = payload.get("formula") or ""
            sid = row.get("id") or ""
            cache.pop(uname, section)
            return RedirectResponse(
                "/brachy-source-qa?section=%s&msg=Saved+to+history&sid=%s" % (section, sid),
                303,
            )
        except Exception as e:
            print("save_last:", e)
            return RedirectResponse(
                "/brachy-source-qa?section=%s&msg=Save+error" % section,
                303,
            )

    print("brachy_qa_save_last: OK")
    return True
