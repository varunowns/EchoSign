# EchoSign — Real-Time Sign Language Translator

[![Python](https://img.shields.io/badge/python-3.10-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)]()
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10-cyan)]()
[![Next.js](https://img.shields.io/badge/Next.js-13.5-black)]()

Real-time American Sign Language (ASL) alphabet recognition using MediaPipe hand tracking, a Random Forest static classifier, and an LSTM sequence model, served via WebSocket to a React dashboard.

---

## Architecture

The system follows a 5-milestone pipeline:

```
Webcam -> M1 (Keypoints) -> M2 (Frame Classifier) -> M4 (Sequence Model) -> M5 (Post-Process) -> UI
```

| Module | Component | Description |
|--------|-----------|-------------|
| **M1** | `M1_improved.py` | MediaPipe HandLandmarker + PoseLandmarker extracts 300D keypoint vector, normalized relative to shoulder midpoint |
| **M2** | `m2_static_classifier.py` | Random Forest classifier on single-frame 82-feature vectors (primary real-time predictor, 26 ASL letters) |
| **M3** | `m3_data_pipeline.py` | Data collection and session-based train/val/test splits (no temporal leakage) |
| **M4** | `m4_sequence_model.py` | LSTM sequence model with temporal context over 45 frames |
| **M5** | `m5_live_inference.py` | Inference engine with confidence thresholding, cooldown debounce, WebSocket integration |

**Post-processing (applied in order):**
1. Confidence thresholding (>= 0.15)
2. Cooldown-based debounce (re-commits same sign every ~1s at 30 FPS)
3. Frontend 3-frame stability check (prevents flicker)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 13.5, React 18, Framer Motion, Tailwind CSS, Three.js (NeuralSphere) |
| **Backend** | Python 3.10, FastAPI, Uvicorn, WebSockets |
| **ML Pipeline** | MediaPipe Tasks, scikit-learn (Random Forest), PyTorch (LSTM) |

---

## Quick Start

### Prerequisites
- Python 3.10 (3.11 works; **not 3.12+**)
- Node.js >= 18
- Webcam

### Backend

```bash
cd backend
python -m venv venv_310
source venv_310/Scripts/activate   # Windows PowerShell
pip install -r requirements.txt
python backend_api.py
```

API at `http://localhost:8000`. Swagger docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:3000`.

### Docker

```bash
docker-compose up --build
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Pipeline status (M1, M2, M4 readiness) |
| `GET` | `/api/models` | Available models and latency |
| `POST` | `/api/infer` | Single-frame inference |
| `POST` | `/api/debug-frame` | Frame quality + MediaPipe diagnostics |
| `POST` | `/api/config` | Update runtime configuration |
| `WS` | `/ws/live` | Real-time video stream -> predictions (30 FPS) |

### WebSocket Protocol

```
Client -> Server:  base64-encoded PNG frame
Server -> Client:  {"type": "inference_result", "prediction": "A", "confidence": 0.85, ...}
```

---

## Model Training

Train on real collected data for production use:

```bash
# 1. Collect training data
python backend/data_collector.py --label A --duration 1.5

# 2. Train frame classifier
python backend/m2_static_classifier.py --train --data-dir data/raw

# 3. Train sequence model
python backend/m3_data_pipeline.py
python backend/m4_sequence_model.py --train
```

**Important:** Always split by recording session, not by random frame. Consecutive frames from the same recording are highly correlated; random splits inflate accuracy by ~30% on validation but fail in production.

---

## Project Structure

```
EchoSign/
  backend/                       # Python ML pipeline + API
    backend_api.py               # FastAPI server (entry point)
    backend_api_mock.py          # Mock server for frontend dev
    M1_improved.py               # MediaPipe keypoint extraction
    m2_static_classifier.py      # Random Forest frame classifier
    m3_data_pipeline.py          # Data loading + session splits
    m4_sequence_model.py         # PyTorch LSTM sequence model
    m5_live_inference.py         # Real-time inference engine
    data_collector.py            # Webcam data collection tool
    requirements.txt             # Python dependencies
    models/                      # Trained model files
    data/                        # Training data (gitignored)
  frontend/                      # Next.js dashboard
    app/page.tsx                 # Main dashboard component
    hooks/useBackendInference.ts # WebSocket + health hook
    components/echosign/         # UI components
    lib/api.ts                   # API client
  docker-compose.yml             # Multi-service orchestration
  LICENSE                        # MIT
  README.md
```

---

## Key Design Decisions

- **Python 3.10 pinned** -- ML packages (OpenCV, MediaPipe, PyTorch) lag Python releases by 6-12 months; no wheels exist for 3.12+
- **Session-based data splits** prevent temporal leakage between train and test sets
- **Cooldown post-processor** prevents transcript flooding while keeping the UI responsive for held signs
- **Frontend stabilizer** (3-frame hold) adds a second gate against flickering predictions
- **PNG encoding** for lossless frame transmission (quality > bandwidth for reliable MediaPipe detection)

---

## License

MIT
