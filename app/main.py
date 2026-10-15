"""
TRS-398 Dosimetry App - FastAPI entry point
Stage 1: Basic skeleton
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="TRS-398 Dosimetry",
    description="Absolute dosimetry for photons, electrons and brachytherapy (IAEA TRS-398)",
    version="0.1.0",
)


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>TRS-398 Dosimetry</title>
            <style>
                body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
                h1 { color: #1a365d; }
                .status { background: #ebf8ff; padding: 12px 16px; border-radius: 8px; }
            </style>
        </head>
        <body>
            <h1>TRS-398 Dosimetry App</h1>
            <div class="status">
                <strong>Stage 1 active</strong><br>
                Pure calculation library for photon absolute dosimetry is ready.<br>
                FastAPI skeleton is running.
            </div>
            <p>Next: Stage 2 – API endpoints + simple calculation UI.</p>
            <p><a href="/docs">OpenAPI docs</a></p>
        </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "stage": 1, "modules": ["photon"]}
