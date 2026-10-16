"""UX routes: detector select on measurement, TPR energy picker."""

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models import list_detectors, get_detector, get_beam, get_linac, list_beams, get_default_calc_profile
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

    @app.get("/session/{sid}/tpr-select", response_class=HTMLResponse)
    async def tpr_select(request: Request, sid: str):
        user = _require(request)
        if not user:
            return _login()
        sess = get_session(sid)
        if not sess:
            raise HTTPException(404)
        photon_beams = list_beams(linac_id=sess.linac_id, modality="photon")
        return templates.TemplateResponse(
            request=request, name="session_tpr_select.html",
            context={
                "session": sess,
                "linac": get_linac(sess.linac_id),
                "photon_beams": photon_beams,
                "current_user": user,
            },
        )

    @app.post("/session/{sid}/energy/{bid}/set-detector")
    async def set_detector(request: Request, sid: str, bid: str, detector_id: str = Form(...)):
        user = _require(request)
        if not user:
            return _login()
        sess = get_session(sid)
        if not sess or not get_beam(bid):
            raise HTTPException(404)
        if detector_id and get_detector(detector_id):
            sess.detector_id = detector_id
        return RedirectResponse(f"/session/{sid}/energy/{bid}", 303)

    # Enhance GET energy form: inject detectors list by replacing route
    to_remove = []
    for r in app.router.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", set()) or set()
        if path == "/session/{sid}/energy/{bid}" and "GET" in methods:
            to_remove.append(r)
    for r in to_remove:
        app.router.routes.remove(r)

    @app.get("/session/{sid}/energy/{bid}", response_class=HTMLResponse)
    async def energy_form_v2(request: Request, sid: str, bid: str):
        user = _require(request)
        if not user:
            return _login()
        sess, beam = get_session(sid), get_beam(bid)
        if not sess or not beam:
            raise HTTPException(404)
        detector = get_detector(sess.detector_id) if sess.detector_id else None
        beam_qi = sess.beam_quality_index.get(bid) or beam.quality_index
        prior = list(sess.beam_readings.get(bid, [])) if hasattr(sess, "beam_readings") else []
        return templates.TemplateResponse(
            request=request, name="session_energy_calc.html",
            context={
                "session": sess,
                "beam": beam,
                "linac": get_linac(sess.linac_id),
                "detector": detector,
                "detectors": list_detectors(),
                "beam_qi": beam_qi,
                "profile": get_default_calc_profile(),
                "result": None,
                "status": None,
                "current_user": user,
                "prior_readings": prior[:-1] if len(prior) > 1 else [],
                "last_reading": prior[-1] if prior else None,
                "last_mu": 100,
            },
        )
