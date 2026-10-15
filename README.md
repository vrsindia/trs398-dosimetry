# TRS-398 Dosimetry App

**IAEA TRS-398 Absolute Dosimetry** for high-energy photons and electrons + **Brachytherapy well-chamber source strength** determination.

Single-physicist private tool (public repository).  
Built with FastAPI + pure Python calculation library.  
Designed for zero-cost hosting on Render free tier.

> **Important**: This software is for educational / developmental use.  
> It has **not** been validated for clinical decision-making.  
> Always cross-check results with your institutional procedures and calibrated systems.

---

## Live Modules

| Module | Path | Status |
|--------|------|--------|
| Photon Absolute Dosimetry (TRS-398) | `/photon` | Complete |
| Electron Absolute Dosimetry (TRS-398) | `/electron` | Complete |
| Brachytherapy Well-Chamber (S_K) | `/brachy` | Complete |
| Simple Chamber Registry | In-memory | Complete |
| API endpoints | `/api/photon`, `/api/electron`, `/api/brachy` | Complete |

---

## Stages Completed

1. Project skeleton + pure Photon calculation library  
2. FastAPI + HTML UI for Photon  
3. Electron module + UI + API  
4. Brachytherapy well-chamber module + UI + API  
5. In-memory chamber registry + uncertainty helpers  
6. (Uncertainty notes included in calculation library)  
7. GitHub Actions CI + Render Blueprint ready

---

## Quick Start (Local)

```bash
git clone https://github.com/vrsindia/trs398-dosimetry.git
cd trs398-dosimetry
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

---

## Deploy to Render (Free Tier)

1. Go to [render.com](https://render.com) and create a free account.
2. New → Web Service → Connect the GitHub repository `vrsindia/trs398-dosimetry`.
3. Render will detect `render.yaml` or you can set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Create the service. The free tier will sleep after inactivity (cold start ~15-30 s).

Alternatively use the Blueprint (`render.yaml`) for one-click setup.

---

## Project Structure

```
app/
├── main.py                 # FastAPI app + routes
├── chambers.py             # Simple in-memory chamber registry
├── calculations/
│   ├── photon.py           # TRS-398 photon absolute dose
│   ├── electron.py         # TRS-398 electron absolute dose
│   ├── brachy.py           # Well-chamber air kerma strength
│   └── uncertainty.py      # Basic uncertainty helpers
└── templates/              # Jinja2 HTML UI
tests/                      # Unit tests for all calculation modules
.github/workflows/ci.yml    # GitHub Actions – runs pytest on every push
render.yaml                 # Render free-tier blueprint
```

---

## Physics Notes

- All calculation functions are **pure** (no side effects, no I/O).  
- Easy to unit-test and later extract into a separate package.  
- Formulas follow IAEA TRS-398 structure.  
- Brachytherapy module implements practical well-chamber S_K determination with optional decay correction.

---

## License

MIT – for personal and educational use.
