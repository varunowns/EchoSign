"""
EchoSign Backend API - FastAPI Wrapper
=======================================
Connects frontend UI to M1-M5 sign language recognition pipeline

Endpoints:
- POST /api/infer - Single frame inference
- WebSocket /ws/live - Real-time video stream + inference
- GET /api/models - List available models
- POST /api/config - Update configuration
"""

from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import torch
import asyncio
import base64
from typing import Optional
import logging

# Import M1-M5 pipeline components
try:
    from m5_live_inference import LiveInferenceEngine, PostProcessor
    from m2_static_classifier import StaticGestureClassifier, FrameFeatureExtractor
    from m4_sequence_model import SequenceModel
except ImportError as e:
    print(f"Warning: Could not import pipeline components: {e}")
    print("Make sure M1-M5 files are in the same directory or PYTHONPATH")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="EchoSign API",
    description="Real-Time Sign Language Recognition",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in dev; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global inference engine
inference_engine = None
classifier_m2 = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class BackendConfig:
    """Configuration for backend inference."""
    def __init__(self):
        self.use_m2 = True  # Static classifier
        self.use_m4 = False  # LSTM (if trained)
        self.confidence_threshold = 0.7
        self.smoothing_window = 5
        self.debounce_frames = 3
        self.model_path_m2 = "models/asl_alphabet.pkl"
        self.model_path_m4 = "models/sequence_model.pt"


config = BackendConfig()


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup."""
    global inference_engine, classifier_m2

    logger.info("Initializing EchoSign backend...")

    try:
        # Initialize live inference engine (M1-M5)
        inference_engine = LiveInferenceEngine(model_path=None)
        logger.info("✓ M1-M5 pipeline initialized")
    except Exception as e:
        logger.warning(f"Could not initialize M1-M5 pipeline: {e}")

    try:
        # Load M2 classifier if available
        classifier_m2 = StaticGestureClassifier.load(config.model_path_m2)
        config.use_m2 = True
        logger.info("✓ M2 classifier loaded")
    except Exception as e:
        logger.warning(f"M2 classifier not available: {e}")
        config.use_m2 = False

    logger.info("Backend startup complete")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "m1_ready": inference_engine is not None,
        "m2_ready": classifier_m2 is not None and config.use_m2,
        "m4_ready": config.use_m4,
        "device": str(device)
    }


@app.get("/api/models")
async def get_models():
    """Get available models and their status."""
    return {
        "m1": {
            "name": "Keypoint Extraction",
            "status": "ready" if inference_engine else "not_loaded",
            "latency_ms": "30-50"
        },
        "m2": {
            "name": "Static Classifier (ASL Alphabet)",
            "status": "ready" if config.use_m2 else "not_loaded",
            "classes": 26,
            "latency_ms": "<5"
        },
        "m4": {
            "name": "LSTM Sequence Model",
            "status": "ready" if config.use_m4 else "not_loaded",
            "latency_ms": "50-100"
        },
        "m5": {
            "name": "Real-Time Inference Engine",
            "status": "ready" if inference_engine else "not_loaded",
            "features": ["smoothing", "debounce", "confidence_threshold"]
        }
    }


@app.post("/api/infer")
async def infer_frame(file: UploadFile = File(...)):
    """
    Infer on a single uploaded frame.

    Input: Image file (JPEG/PNG)
    Output: Prediction + confidence
    """
    if not classifier_m2 or not config.use_m2:
        return JSONResponse(
            {"error": "M2 classifier not available"},
            status_code=503
        )

    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return JSONResponse({"error": "Invalid image"}, status_code=400)

        # In production, would extract keypoints from frame here
        # For now, return placeholder
        return {
            "prediction": "A",
            "confidence": 0.95,
            "model": "m2",
            "latency_ms": 5
        }

    except Exception as e:
        logger.error(f"Inference error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/config")
async def update_config(new_config: dict):
    """Update backend configuration."""
    for key, value in new_config.items():
        if hasattr(config, key):
            setattr(config, key, value)
            logger.info(f"Updated config: {key} = {value}")

    return {"status": "updated", "config": config.__dict__}


@app.websocket("/ws/live")
async def websocket_live_inference(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video streaming + inference.

    Protocol:
    - Client sends: Base64-encoded frame (JPEG)
    - Server sends: {"prediction": "A", "confidence": 0.95, ...}
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive frame data
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            try:
                # Decode base64 frame
                frame_data = base64.b64decode(data)
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is None:
                    await websocket.send_json({"error": "Invalid frame"})
                    continue

                # TODO: Extract keypoints from frame (M1)
                # TODO: Run inference (M2 or M4)
                # TODO: Post-process (M5)

                # Placeholder response
                response = {
                    "type": "inference_result",
                    "prediction": "A",
                    "confidence": 0.92,
                    "model": "m2",
                    "timestamp": "2026-07-14T13:00:00Z"
                }

                await websocket.send_json(response)

            except Exception as e:
                logger.error(f"Frame processing error: {e}")
                await websocket.send_json({"error": str(e)})

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        logger.info("WebSocket client disconnected")


@app.post("/api/train-m2")
async def train_m2_endpoint(data_dir: str = "data/raw"):
    """
    Trigger M2 classifier training.

    Returns training status and accuracy.
    """
    # This would call m2_static_classifier.py --train
    return {
        "status": "training_started",
        "data_dir": data_dir,
        "message": "Check backend logs for progress"
    }


@app.post("/api/collect-data")
async def collect_data_endpoint(label: str, duration: float = 1.5):
    """
    Start data collection for a gesture/letter.

    Returns collection status.
    """
    return {
        "status": "collection_ready",
        "label": label,
        "duration": duration,
        "message": "Use /api/ws/data-collection to stream frames"
    }


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("EchoSign Backend API")
    print("="*60)
    print("\nStarting server on http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    print("WebSocket: ws://localhost:8000/ws/live")
    print("="*60 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
