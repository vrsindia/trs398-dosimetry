# TRS-398 Dosimetry App

**IAEA TRS-398 Absolute Dosimetry** for high-energy photons and electrons + Brachytherapy source strength determination.

Private single-physicist tool (public repository for transparency and easy deployment).

## Current Status

**Stage 1 completed**  
- Project skeleton  
- Pure Python calculation library for TRS-398 Photon absolute dosimetry  
- Basic FastAPI skeleton  
- Unit tests for photon module

## Planned Stages

1. **Stage 1** (done): Skeleton + TRS-398 Photon pure calculation library  
2. **Stage 2**: FastAPI endpoints + simple HTML UI for photon dosimetry  
3. **Stage 3**: Electron beam module (TRS-398)  
4. **Stage 4**: Brachytherapy well-chamber source strength  
5. **Stage 5**: Chamber & certificate management + Supabase  
6. **Stage 6**: Full uncertainty budget + PDF report  
7. **Stage 7**: Render deployment + GitHub Actions CI

## Tech Stack

- Backend: FastAPI (Python)
- Calculations: Pure Python + NumPy (no external physics libraries)
- Database (later): Supabase (free tier)
- Hosting: Render (free tier)
- CI/CD: GitHub Actions

## Local Development

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Physics Reference

IAEA Technical Reports Series No. 398 (2000)  
*Absorbed Dose Determination in External Beam Radiotherapy*

## License

MIT (for personal/educational use). Not intended for clinical use without full validation.
