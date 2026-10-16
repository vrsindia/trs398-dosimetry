"""UX routes: energy GET with detector from session only; TPR optional."""

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models import get_detector, get_beam, get_linac, get_default_calc_profile
from app.session import get_session
from app.auth import get_user_by_token, PERM_CALCULATE

COOKIE = "dosepro_session"


def register_ux_routes(app, templates):

    def _user(request: Request):
        return get_user_by_token(request.cookies.get(COOKIE))

    def _require(request: Request):
        user = _user(request)
        if not user or not user.has(PERM_CALCULATE):
            return None
        return user

    def _login():
        return RedirectResponse("/login", 303)

    # Replace GET energy form
    to_remove = []
    for r in list(app.router.routes):
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", set()) or set()
        if path == "/session/{sid}/energy/{bid}" and "GET" in methods:
            to_remove.append(r)
    for r in to_remove:
        try:
            app.router.routes.remove(r)
        except ValueError:
            pass

    @app.get("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
    async def energy_form_v2(request: Request, sid: str, bid: str):
        user = _require(request)
        if not user:
            return _login()
        sess, beam = get_session(sid), get_beam(bid)
        if not sess or not beam:
            raise HTTPException(404)
        detector = get_detector(sess.detector_id) if getattr(sess, "detector_id", None) else None
        beam_qi = None
        if hasattr(sess, "beam_quality_index") and sess.beam_quality_index:
            beam_qi = sess.beam_quality_index.get(bid)
        if beam_qi is None:
            beam_qi = getattr(beam, "quality_index", None)
        prior = []
        if hasattr(sess, "beam_readings") and sess.beam_readings:
            prior = list(sess.beam_readings.get(bid, []))
        return templates.TemplateResponse(
            request=request, name="session_energy_calc.html",
            context={
                "session": sess,
                "beam": beam,
                "linac": get_linac(sess.linac_id),
                "detector": detector,
                "beam_qi": beam_qi,
                "profile": get_default_calc_profile(),
                "result": None,
                "status": None,
                "current_user": user,
                "prior_readings": prior[:-1] if len(prior) > 1 else [],
                "last_reading": prior[-1] if prior else None,
                "last_mu": 100,
                "error": None,
            },
        )
