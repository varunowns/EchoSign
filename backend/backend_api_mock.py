"""
EchoSign Mock Backend API - FastAPI
====================================
Lightweight mock backend for UI preview (no heavy ML dependencies)
Works on Python 3.14 without numpy/torch/cv2 issues

Run: python backend_api_mock.py
Visit: http://localhost:8000/docs
"""

from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import random
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="EchoSign API (Mock)",
    description="Real-Time Sign Language Recognition - Mock Backend",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock ASL alphabet for predictions
ASL_ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

class BackendConfig:
    """Configuration for backend inference."""
    def __init__(self):
        self.confidence_threshold = 0.7
        self.smoothing_window = 5
        self.debounce_frames = 3

config = BackendConfig()

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("🚀 EchoSign Mock Backend Starting...")
    logger.info("✓ Mock models loaded (no ML overhead)")
    logger.info("Ready for UI preview at http://localhost:3000")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "EchoSign Backend API (Mock)"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "m1_ready": True,
        "m2_ready": True,
        "m4_ready": False,
        "device": "cpu",
        "backend": "mock"
    }

@app.get("/api/models")
async def get_models():
    """Get available models and their status."""
    return {
        "m1": {
            "name": "Keypoint Extraction",
            "status": "mock",
            "latency_ms": "30-50"
        },
        "m2": {
            "name": "Static Classifier (ASL Alphabet)",
            "status": "mock",
            "classes": 26,
            "latency_ms": "<5"
        },
        "m4": {
            "name": "LSTM Sequence Model",
            "status": "not_loaded",
            "latency_ms": "50-100"
        },
        "m5": {
            "name": "Real-Time Inference Engine",
            "status": "mock",
            "features": ["smoothing", "debounce", "confidence_threshold"]
        }
    }

@app.post("/api/config")
async def update_config(config_update: dict):
    """Update backend configuration."""
    for key, value in config_update.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return {"status": "updated", "config": config.__dict__}

@app.post("/api/infer")
async def infer_frame(file: UploadFile = File(...)):
    """
    Infer on a single uploaded frame (mock).
    Returns random ASL letter with mock confidence.
    """
    # Read and ignore the file content (just for mock)
    content = await file.read()

    # Return mock prediction
    prediction = random.choice(ASL_ALPHABET)
    confidence = random.uniform(0.75, 0.98)

    return {
        "prediction": prediction,
        "confidence": float(round(confidence, 2)),
        "timestamp": None,
        "processing_time_ms": random.randint(20, 50)
    }

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video stream inference (mock).
    Client sends frames; server returns predictions.
    """
    await websocket.accept()
    logger.info("✓ WebSocket client connected")

    frame_count = 0
    try:
        while True:
            # Receive frame data from client
            data = await websocket.receive_text()
            frame_count += 1

            # Mock inference: return random prediction every 5 frames
            if frame_count % 5 == 0:
                prediction = random.choice(ASL_ALPHABET)
                confidence = random.uniform(0.75, 0.98)

                response = {
                    "frame": frame_count,
                    "prediction": prediction,
                    "confidence": float(round(confidence, 2)),
                    "processing_time_ms": random.randint(20, 50),
                    "status": "success"
                }
                await websocket.send_json(response)
            else:
                # Send heartbeat for frames without prediction
                await websocket.send_json({
                    "frame": frame_count,
                    "status": "processing",
                    "prediction": None
                })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info(f"✗ WebSocket client disconnected after {frame_count} frames")

@app.get("/api/docs")
async def get_docs():
    """Documentation endpoint."""
    return {
        "backend": "mock",
        "endpoints": {
            "GET /api/health": "Check backend status",
            "GET /api/models": "List available models",
            "POST /api/config": "Update configuration",
            "POST /api/infer": "Inference on single frame",
            "WebSocket /ws/live": "Real-time video stream",
            "GET /docs": "Interactive API docs (Swagger UI)"
        }
    }

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("EchoSign Backend API (Mock)")
    print("=" * 60)
    print()
    print("[*] Server:       http://localhost:8000")
    print("[*] API Docs:     http://localhost:8000/docs")
    print("[*] WebSocket:    ws://localhost:8000/ws/live")
    print()
    print("=" * 60)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
