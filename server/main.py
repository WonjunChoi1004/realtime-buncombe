import os, json, joblib
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator
from fastapi.middleware.cors import CORSMiddleware

ARTIFACT_PATH = os.getenv("MODEL_PATH", "artifacts/model.joblib")
bundle = joblib.load(ARTIFACT_PATH)
pipe = bundle["model"]
FEATURES: List[str] = bundle["feature_order"]

app = FastAPI(title="Realtime Landslide Predictor", version=bundle["meta"].get("version","0"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

class PredictRequest(BaseModel):
    # Keep keys aligned with FEATURES
    rain_1d: float
    rain_7d: float
    slope: float

    @field_validator("*")
    @classmethod
    def finite(cls, v):
        if v is None: raise ValueError("Missing value")
        return float(v)

class PredictResponse(BaseModel):
    prob: float
    label: int

def _vectorize(d: dict):
    return [[d[k] for k in FEATURES]]

@app.get("/health")
def health():
    return {"status":"ok", "features":FEATURES}

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    X = _vectorize(req.model_dump())
    proba = float(pipe.predict_proba(X)[0][1])
    label = int(proba >= 0.5)
    return {"prob": proba, "label": label}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            X = _vectorize({k: float(data[k]) for k in FEATURES})
            proba = float(pipe.predict_proba(X)[0][1])
            label = int(proba >= 0.5)
            await ws.send_text(json.dumps({"prob": proba, "label": label}))
    except WebSocketDisconnect:
        return
