# Claude Code Instructions - EchoSign Project

**Project**: Real-Time Sign Language Translator (EchoSign)  
**Language**: Python + JavaScript  
**Platform**: Windows 11 + PowerShell  
**Tech Stack**: FastAPI, Next.js React, PyTorch LSTM, MediaPipe  
**Last Updated**: 2026-07-14

---

## Critical: Python Version & Dependencies

**ALWAYS use Python 3.10 LTS, NOT 3.14 or newer.**

Reason: ML packages (opencv, mediapipe, torch, scikit-learn) lack wheels for Python 3.14. Build-from-source requires Microsoft Visual C++. See [[V:\Obsidian\Projects\EchoSign\bugs-and-fixes.md#Python 3.14 Incompatibility|bugs-and-fixes: Python 3.14]].

When dependency conflicts arise:
1. Pin exact versions for critical packages: `torch==2.13.0`, `mediapipe==0.10.35`, `numpy<2.0.0`
2. Loose-pin infrastructure: `fastapi>=0.104.0`, `uvicorn>=0.24.0`
3. Update requirements.txt comment with rationale
4. Re-validate when upgrading Python

See [[V:\Obsidian\Projects\EchoSign\setup-and-environment.md|setup-and-environment.md]] for exact setup steps.

---

## Backend Development

### When Backend Fails to Start

**Do NOT try to "fix" the full backend_api.py immediately.**

If `backend_api.py` fails due to heavy imports (cv2, torch, mediapipe):
1. Use `backend_api_mock.py` to unblock frontend testing
2. Diagnostic command: `python -c "import cv2; import torch; print('OK')"`
3. If that fails, check Python version (`python --version`) — must be 3.10
4. Fix dependencies in isolation, then retry full backend

Reason: Monolithic imports cascade; separating API contract from implementation unblocks parallel work.

### WebSocket & Real-Time

- Backend runs on port 8000 by default
- Frontend connects via `ws://localhost:8000/ws/live`
- Add connection retry logic in frontend (exponential backoff)
- Log all startup status messages to help diagnose connection timeouts

### Post-Processing is Non-Optional

Never output raw model predictions. Always apply:
1. Confidence thresholding (≥0.7)
2. Temporal smoothing (majority vote over 5 recent frames)
3. Debounce (require 3 stable predictions before commit)

See [[V:\Obsidian\Shared\lessons-learned.md#Post-Processing|lessons-learned: Post-Processing]].

---

## Data & Training

### Train/Val/Test Splits: Use Sessions, Not Frames

**Critical**: Split by recording session, never by random frame.

Reason: Consecutive frames from same session are highly correlated. Random splits cause temporal leakage; model accuracy inflates by ~30% but real-world performance drops.

In M3 data pipeline:
```python
# Correct:
train_sessions, test_sessions = train_test_split(sessions, test_size=0.2)
# Assign frames by session membership

# Wrong:
train_frames, test_frames = train_test_split(all_frames, test_size=0.2)  # ← Leaks
```

See [[V:\Obsidian\Projects\EchoSign\dataset-notes.md|dataset-notes.md]].

### Synthetic Data = Pipeline Validation Only

Synthetic keypoints are for:
- ✅ Testing M1→M2→M4→output runs end-to-end
- ✅ Hyperparameter search (learning rate, batch size)
- ❌ Accuracy claims
- ❌ Production readiness
- ❌ Feature validation (will fail on real data)

Always annotate synthetic results: "95% (synthetic data; pending real-world validation)".

### Feature Normalization: Shoulder-Relative

All keypoint features must normalize relative to shoulder midpoint + shoulder width:

```python
shoulder_center = (pose[11] + pose[12]) / 2
shoulder_width = ||pose[12] - pose[11]||
normalized_keypoints = (keypoints - shoulder_center) / shoulder_width
```

This makes models robust to:
- Camera distance (1m vs 2m away)
- Person height (tall vs short)
- Spatial location (left vs right side of frame)

See [[V:\Obsidian\Projects\EchoSign\architecture.md|architecture.md#Data & Feature Engineering]].

---

## Frontend Development

### Next.js Setup

Environment variable for backend connection:
```
REACT_APP_API_URL=http://localhost:8000
```

Never hardcode localhost; use env var so it works on production/Docker.

### UI States to Test

- **IDLE**: No prediction (system standby)
- **PROCESSING**: Frame received, inference in progress
- **PREDICTION**: Confident sign detected (show with confidence %)
- **ERROR**: Backend unavailable or malformed response

Mock backend returns random predictions for each state. Use for UI regression testing.

---

## Windows-Specific Gotchas

### PowerShell Encoding

Avoid emoji in CLI output. Use ASCII symbols:
- ✅ `[*] Server started` instead of 🚀
- ✅ `[✓] Backend ready` instead of ✅
- ✅ `[X] Error occurred` instead of ❌

**Why**: Windows PowerShell 5.1 uses cp1252 encoding; emoji (U+1F310+) not supported.

### Path Handling

Always use forward slashes in glob patterns / file operations:
```python
# Correct
Path("V:/EchoSign/data/raw/*.json")

# Avoid backslashes in code (Windows interprets \ as escape)
Path("V:\EchoSign\data\raw\*.json")  # ← Wrong
```

### Port Conflicts

Before starting backend, check if port 8000 is in use:
```powershell
netstat -ano | findstr ":8000"
```

If occupied, kill process: `taskkill /PID <PID> /F` or use `--port 8001`.

---

## API Design & Documentation

### Every HTTP Endpoint Needs Docstring

Use FastAPI's auto-docs at `/docs`. Example:

```python
@app.post("/api/infer")
async def infer_frame(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(0.7, ge=0.0, le=1.0)
) -> InferenceResult:
    """
    Classify a single frame.
    
    Args:
        file: JPEG/PNG image
        confidence_threshold: Only return predictions ≥ this value
    
    Returns:
        InferenceResult with prediction, confidence, latency_ms
    """
```

Document all config parameters (thresholds, model paths, smoothing window) in backend startup logs.

---

## Testing & Validation

### Before Claiming Model Works

- [ ] Real data collected (≥20 samples per class)
- [ ] Train/val/test split by session (verified ∩ = ∅)
- [ ] Confusion matrix + per-class accuracy reported (not just overall)
- [ ] Tested on video outside controlled environment
- [ ] Latency measured end-to-end (M1→M4→M5 pipeline)
- [ ] Post-processing thresholds tuned on validation set

Synthetic data only confirms pipeline runs; real validation is non-negotiable for production claims.

---

## Deployment Checklist

- [ ] `backend/requirements.txt` pinned and tested on Python 3.10
- [ ] `frontend/.env.production` set (API_URL points to production backend)
- [ ] `docker-compose.yml` defines all services + `depends_on` order
- [ ] API docs at `/docs` accurate and up-to-date
- [ ] Health check endpoint (`/api/health`) working
- [ ] WebSocket connection times out gracefully (not forever)
- [ ] Startup logs show backend + frontend + model status

---

## Related Documentation

- [[V:\Obsidian\Projects\EchoSign\architecture.md|architecture.md]] — System design & rationale
- [[V:\Obsidian\Projects\EchoSign\decisions-log.md|decisions-log.md]] — Tech choices with context
- [[V:\Obsidian\Projects\EchoSign\bugs-and-fixes.md|bugs-and-fixes.md]] — Issues + resolutions
- [[V:\Obsidian\Projects\EchoSign\model-training-notes.md|model-training-notes.md]] — M2/M4 details
- [[V:\Obsidian\Shared\lessons-learned.md|lessons-learned.md]] — Cross-project insights

---

**Remember**: When stuck, check the Obsidian vault first. Decisions, bugs, and lessons are documented with rationale.
