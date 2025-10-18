#!/usr/bin/env python3
"""
FastAPI backend for the Buncombe real-time landslide project.
Step 1: expose latest GeoJSON and metadata to the front end.
"""

from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

# -----------------------------------------------------------
# Initialize app
# -----------------------------------------------------------
app = FastAPI(title="Buncombe Landslide Prediction API")

# -----------------------------------------------------------
# Static mount: serve raw GeoJSONs and related outputs
# -----------------------------------------------------------
# Folder structure expected:
# predictions/
#   ├── latest.geojson
#   ├── latest.json
#   └── YYYY-MM-DD/predictions.geojson
app.mount("/predictions", StaticFiles(directory="predictions"), name="predictions")

# (optional) serve the whole www folder if you later add assets (css/js/images)
app.mount("/www", StaticFiles(directory="www"), name="www")

# -----------------------------------------------------------
# Helper: load JSON safely
# -----------------------------------------------------------
def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to read {path.name}: {e}"}

# -----------------------------------------------------------
# Root route: serve the front-end page
# -----------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = Path("www/index.html")
    if not index_path.exists():
        # fallback placeholder if index.html not present
        return HTMLResponse(
            """
            <html><body style="font-family:sans-serif">
              <h2>🚧 Landslide Nowcast Backend</h2>
              <p>Place your front-end at <code>www/index.html</code>.</p>
              <ul>
                <li><a href="/predictions/latest.geojson">/predictions/latest.geojson</a></li>
                <li><a href="/api/latest">/api/latest</a></li>
              </ul>
            </body></html>
            """,
            status_code=200,
        )
    return index_path.read_text(encoding="utf-8")

# -----------------------------------------------------------
# API: metadata for the latest prediction
# -----------------------------------------------------------
@app.get("/api/latest")
def get_latest_metadata():
    """Return metadata describing the most recent prediction run."""
    meta_path = Path("predictions/latest.json")
    meta = _read_json(meta_path)
    if meta is None:
        return JSONResponse(
            {"error": "latest.json not found", "path": str(meta_path)}, status_code=404
        )
    return JSONResponse(meta)

# -----------------------------------------------------------
# API: return the latest GeoJSON file directly
# -----------------------------------------------------------
@app.get("/api/latest_geojson")
def get_latest_geojson():
    """Serve the latest GeoJSON (for easy fetch from front-end JS)."""
    geo_path = Path("predictions/latest.geojson")
    if not geo_path.exists():
        return JSONResponse(
            {"error": "latest.geojson not found", "path": str(geo_path)}, status_code=404
        )
    return FileResponse(geo_path, media_type="application/geo+json")

# -----------------------------------------------------------
# Health check / status endpoint
# -----------------------------------------------------------
@app.get("/api/status")
def status():
    """Simple heartbeat endpoint."""
    latest = Path("predictions/latest.json")
    return {
        "service": "buncombe-nowcast",
        "status": "ok" if latest.exists() else "no-latest",
        "latest_exists": latest.exists(),
        "latest_path": str(latest),
    }

# -----------------------------------------------------------
# Run (only if executed directly)
# -----------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
