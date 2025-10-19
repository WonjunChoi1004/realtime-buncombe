import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent.parent  # repo root
WWW_DIR = BASE / "www"
PRED_DIR = BASE / "predictions"
META_PATH = PRED_DIR / "latest.json"  # update daily along with latest.geojson

app = FastAPI(title="Landslide Nowcast Backend")

@app.get("/api/latest")
def latest():
    if not META_PATH.exists():
        raise HTTPException(503, detail="latest.json missing")
    try:
        import json
        with META_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(500, detail=f"failed to read latest.json: {e}")
    return JSONResponse(data, headers={"Cache-Control": "no-store"})

# Static mounts
app.mount("/predictions", StaticFiles(directory=PRED_DIR), name="predictions")
app.mount("/", StaticFiles(directory=WWW_DIR, html=True), name="www")

# Optional root helper page (served only if index.html missing)
@app.get("/health", response_class=JSONResponse)
def health():
    geo = (PRED_DIR / "latest.geojson").exists()
    meta = META_PATH.exists()
    return JSONResponse({"ok": True, "geojson": geo, "meta": meta}, headers={"Cache-Control": "no-store"})

# If you want a simple landing text when index.html isn't present:
@app.get("/_info")
def info():
    return HTMLResponse(
        "<h1>🦺 Landslide Nowcast Backend</h1>"
        "<p>Front-end at <code>www/index.html</code>.</p>"
        "<ul>"
        "<li><a href='/predictions/latest.geojson'>/predictions/latest.geojson</a></li>"
        "<li><a href='/api/latest'>/api/latest</a></li>"
        "</ul>"
    )