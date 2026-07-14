# EchoSign Backend-Frontend Integration Guide

**Status**: Backend API ready, Frontend integration instructions

---

## Architecture

```
Frontend (React/Bolt.new)
    ↓ WebSocket
Backend (FastAPI)
    ↓ Python
M1-M5 Pipeline (PyTorch + MediaPipe)
    ↓
Predictions → UI Display
```

---

## Setup Instructions

### Step 1: Install Backend Dependencies

```bash
cd V:\EchoSign
pip install fastapi uvicorn websockets python-multipart
```

### Step 2: Start Backend API

```bash
python backend_api.py
```

**Expected output**:
```
==============================
EchoSign Backend API
==============================

Starting server on http://localhost:8000
API docs: http://localhost:8000/docs
WebSocket: ws://localhost:8000/ws/live
==============================
```

### Step 3: Clone and Setup Frontend

```bash
git clone https://github.com/varunowns/ui_for_EchoSign frontend
cd frontend
npm install
npm run dev
```

### Step 4: Connect Frontend to Backend

In your React components, use the `EchoSignClient`:

```jsx
import { useEchoSign } from '../echosign-client'

export function SignLanguageRecognizer() {
  const { client, connected } = useEchoSign()
  const [prediction, setPrediction] = React.useState(null)
  const videoRef = React.useRef()
  const canvasRef = React.useRef()

  // Capture frame from canvas
  const handleCapture = async () => {
    const canvas = canvasRef.current
    if (!canvas || !client) return

    try {
      const result = await client.sendFrame(canvas)
      setPrediction(result.prediction)
      console.log(`Recognized: ${result.prediction} (${result.confidence.toFixed(2)})`)
    } catch (err) {
      console.error('Inference failed:', err)
    }
  }

  return (
    <div>
      <video ref={videoRef} width={640} height={480} />
      <canvas ref={canvasRef} />
      <button onClick={handleCapture}>
        {connected ? 'Capture & Recognize' : 'Connecting...'}
      </button>
      {prediction && <p>Result: {prediction}</p>}
    </div>
  )
}
```

---

## API Endpoints

### REST Endpoints

**GET /api/health**
- Status: Server health check
- Response: `{"status": "healthy", "m1_ready": true, "m2_ready": true, ...}`

**GET /api/models**
- List available models and their status
- Response: Model information with latency specs

**POST /api/infer**
- Single frame inference
- Input: Image file (JPEG/PNG)
- Output: `{"prediction": "A", "confidence": 0.95, ...}`

**POST /api/config**
- Update backend configuration
- Input: `{"confidence_threshold": 0.8, "smoothing_window": 5, ...}`
- Output: Updated config

### WebSocket Endpoint

**WS /ws/live**
- Real-time video stream + inference
- Client sends: Base64-encoded frame
- Server responds: `{"type": "inference_result", "prediction": "A", "confidence": 0.95, ...}`

---

## Frontend Integration Checklist

- [ ] Backend API running on `localhost:8000`
- [ ] Frontend npm dependencies installed
- [ ] `echosign-client.js` copied to frontend project
- [ ] `useEchoSign` hook integrated into main component
- [ ] Video/canvas capture working
- [ ] Frame sending via WebSocket working
- [ ] Predictions displaying in UI
- [ ] Transcript accumulating correctly

---

## Data Flow

```
1. User signals via UI (button click / auto-capture)
2. Canvas captures current frame → convert to base64
3. Send via WebSocket to backend
4. Backend:
   - Decode frame (base64 → numpy array)
   - Extract keypoints (M1)
   - Run inference (M2 or M4)
   - Post-process (smoothing, debounce)
5. Send result back via WebSocket
6. Frontend updates UI with prediction + confidence
7. Accumulate to transcript
```

---

## Configuration

Backend configuration in `backend_api.py`:

```python
config.use_m2 = True                    # Enable M2 static classifier
config.use_m4 = False                   # Enable M4 LSTM (if trained)
config.confidence_threshold = 0.7       # Only predictions > 0.7
config.smoothing_window = 5             # Temporal smoothing frames
config.debounce_frames = 3              # Require 3 stable predictions
config.model_path_m2 = "models/asl_alphabet.pkl"
config.model_path_m4 = "models/sequence_model.pt"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CORS error | Backend CORS middleware allows all origins (dev only) |
| WebSocket timeout | Check firewall; ensure `localhost:8000` accessible |
| Inference error | Check models are in `models/` directory |
| Slow inference | Use GPU: install CUDA-enabled PyTorch |
| Connection refused | Start backend: `python backend_api.py` |

---

## Next: Full Integration

After verifying this works, implement:

1. **Video Stream Handling**
   - Capture continuous frames from camera
   - Send at configurable FPS
   - Display with skeleton overlay (optional)

2. **Transcript Management**
   - Accumulate predictions
   - Handle corrections
   - Save to file/database

3. **UI Features**
   - Confidence display
   - FPS counter
   - Model selector (M2 vs M4)
   - Settings panel

4. **Data Collection Mode**
   - Capture gestures for training
   - Label them in UI
   - Send to backend for storage

---

**Ready to integrate?** Let me know if you need help with any specific component!
