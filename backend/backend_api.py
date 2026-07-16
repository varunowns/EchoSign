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
import base64
import time
import sys
import mediapipe as mp
from pathlib import Path
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
logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
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
BASE_DIR = Path(__file__).resolve().parent


def resolve_existing_path(*relative_paths: str) -> str:
    """Resolve model paths across the repo root and backend/ directories."""
    for rel_path in relative_paths:
        candidate = (BASE_DIR / rel_path).resolve()
        if candidate.exists():
            return str(candidate)
    return str((BASE_DIR / relative_paths[0]).resolve())


class BackendConfig:
    """Configuration for backend inference."""
    def __init__(self):
        self.use_m2 = False  # Static classifier (pickle compatibility issues)
        self.use_m4 = True  # LSTM - primary model
        self.confidence_threshold = 0.7
        self.smoothing_window = 5
        self.debounce_frames = 3
        self.model_path_m2 = resolve_existing_path("models/asl_alphabet.pkl", "../backend/models/asl_alphabet.pkl")
        self.model_path_m4 = resolve_existing_path("models/asl_sequence.pt", "../backend/models/asl_sequence.pt")


config = BackendConfig()


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup."""
    global inference_engine, classifier_m2
    classifier_m2 = None  # may stay None if M2 fails to load

    logger.info("Initializing EchoSign backend...")

    try:
        # Load M2 classifier first (engine needs it)
        classifier_m2 = StaticGestureClassifier.load(config.model_path_m2)
        config.use_m2 = True
        logger.info("[OK] M2 classifier loaded")
    except Exception as e:
        logger.warning(f"M2 classifier not available: {e}")
        config.use_m2 = False

    try:
        # Initialize live inference engine (M1-M5) with M2 classifier
        inference_engine = LiveInferenceEngine(
            model_path=config.model_path_m4,
            m2_classifier=classifier_m2
        )
        config.use_m4 = inference_engine.model is not None
        logger.info("[OK] M1-M5 pipeline initialized")
    except Exception as e:
        logger.warning(f"Could not initialize M1-M5 pipeline: {e}")
        inference_engine = None
        config.use_m4 = False

    logger.info("Backend startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Release backend resources on shutdown."""
    global inference_engine
    if inference_engine is not None:
        inference_engine.close()
        inference_engine = None


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy" if inference_engine is not None else "degraded",
        "m1_ready": inference_engine is not None,
        "m2_ready": classifier_m2 is not None and config.use_m2,
        "m4_ready": inference_engine is not None and inference_engine.model is not None and config.use_m4,
        "device": str(device),
        "num_classes": inference_engine.model.fc.out_features if inference_engine and inference_engine.model is not None and hasattr(inference_engine.model, 'fc') else None
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

    # Reset engine state for new session (clear buffer, counters, post-processor)
    if inference_engine is not None:
        inference_engine.reset()

    frame_count = 0

    try:
        while True:
            # Receive frame data
            try:
                data = await websocket.receive_text()
            except Exception as e:
                logger.error(f"Failed to receive frame: {e}")
                break

            if data == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            try:
                if inference_engine is None:
                    logger.error("Inference engine is None!")
                    await websocket.send_json(
                        {"type": "error", "error": "Inference engine is not initialized."}
                    )
                    continue

                # Decode base64 frame
                try:
                    if "," in data:
                        data = data.split(",", 1)[1]
                    frame_data = base64.b64decode(data)
                    nparr = np.frombuffer(frame_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is None:
                        logger.warning(f"Failed to decode frame {frame_count}")
                        await websocket.send_json({"type": "error", "error": "Invalid frame"})
                        continue
                except Exception as e:
                    logger.error(f"Frame decode error: {e}")
                    await websocket.send_json({"type": "error", "error": f"Decode error: {str(e)}"})
                    continue

                # Process frame through M1-M5 pipeline
                try:
                    response = inference_engine.process_frame(frame)
                    await websocket.send_json(response)
                    frame_count += 1
                    if frame_count % 30 == 0:
                        logger.info(f"Processed {frame_count} frames")
                except Exception as e:
                    logger.error(f"Inference error on frame {frame_count}: {e}", exc_info=True)
                    await websocket.send_json({"type": "error", "error": f"Inference error: {str(e)}"})
                    continue

            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}", exc_info=True)
                try:
                    await websocket.send_json({"type": "error", "error": str(e)})
                except:
                    break

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        logger.info(f"WebSocket client disconnected after {frame_count} frames")


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


@app.post("/api/debug-frame")
async def debug_frame(file: UploadFile = File(...)):
    """
    Debug endpoint: Returns frame quality metrics and MediaPipe detection status.

    Useful for diagnosing why MediaPipe fails to detect hands on browser frames.
    """
    global inference_engine

    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return JSONResponse({"error": "Invalid image"}, status_code=400)

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        contrast = float(gray.std())
        file_size_kb = len(contents) / 1024

        # Run MediaPipe detection
        if inference_engine:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = int(time.time() * 1000)
            hand_result = inference_engine.hand_landmarker.detect_for_video(mp_image, timestamp_ms)
            pose_result = inference_engine.pose_landmarker.detect_for_video(mp_image, timestamp_ms)

            has_hands = hand_result is not None and len(hand_result.hand_landmarks) > 0
            num_hands = len(hand_result.hand_landmarks) if has_hands else 0
            has_pose = pose_result is not None and len(pose_result.pose_landmarks) > 0

            hand_scores = []
            if has_hands:
                for handedness in hand_result.handedness:
                    hand_scores.append(float(handedness[0].score))

            return {
                "status": "ok",
                "frame": {
                    "width": w,
                    "height": h,
                    "file_size_kb": round(file_size_kb, 1),
                    "brightness": round(brightness, 1),
                    "contrast": round(contrast, 1),
                },
                "detection": {
                    "has_hands": has_hands,
                    "num_hands": num_hands,
                    "hand_scores": hand_scores,
                    "has_pose": has_pose,
                }
            }
        else:
            return {
                "status": "inference_engine_not_ready",
                "frame": {
                    "width": w,
                    "height": h,
                    "file_size_kb": round(file_size_kb, 1),
                    "brightness": round(brightness, 1),
                    "contrast": round(contrast, 1),
                },
            }
    except Exception as e:
        logger.error(f"Debug frame error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


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
