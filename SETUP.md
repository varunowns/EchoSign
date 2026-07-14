# EchoSign - Setup & Installation Guide

## System Requirements

- **OS**: Windows, macOS, or Linux
- **Python**: 3.8 or higher
- **Webcam**: Any USB or built-in camera
- **GPU** (optional): CUDA 11.8+ for faster model training
- **Disk Space**: ~100MB for models + ~500MB for training data

---

## Step 1: Environment Setup

### Option A: Conda (Recommended for ML)

```bash
# Create a new conda environment
conda create -n echosign python=3.10

# Activate it
conda activate echosign

# Install PyTorch (CPU or GPU)
# CPU only:
conda install pytorch torchvision torchaudio -c pytorch

# Or GPU (CUDA 11.8):
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
```

### Option B: venv (Lightweight)

```bash
# Create virtual environment
python -m venv echosign_env

# Activate it
# Windows:
echosign_env\Scripts\activate
# macOS/Linux:
source echosign_env/bin/activate
```

---

## Step 2: Install Dependencies

```bash
# Core dependencies
pip install opencv-python mediapipe numpy

# ML/Training
pip install torch scikit-learn

# Utilities
pip install matplotlib scipy pandas

# Optional: Streamlit for UI (M6)
pip install streamlit pyttsx3
```

**Dependency versions** (tested on 2026-07):
```
opencv-python >= 4.8.0
mediapipe >= 0.10.0
numpy >= 1.24.0
torch >= 2.1.0
scikit-learn >= 1.3.0
```

---

## Step 3: Download MediaPipe Models

Models are already in `V:\EchoSign/`:
- `hand_landmarker.task` (7.5MB)
- `pose_landmarker.task` (30MB)

If you need to download them manually:

```bash
cd V:\EchoSign

# Using wget (if available)
wget -O hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task

# Or use PowerShell
$urls = @(
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)
$names = @("hand_landmarker.task", "pose_landmarker.task")
for ($i = 0; $i -lt $urls.Count; $i++) {
    Invoke-WebRequest -Uri $urls[$i] -OutFile $names[$i]
}
```

---

## Step 4: Verify Installation

```bash
# Test imports
python -c "import cv2; import mediapipe; import torch; print('✓ All dependencies loaded')"

# Test M1 (should open webcam)
python M1_improved.py

# Controls:
#   q     = quit
#   s     = print keypoint info
#   SPACE = pause/resume
```

---

## Step 5: First Run Checklist

- [ ] Webcam opens without errors
- [ ] Landmarks visible in real-time (green skeleton)
- [ ] FPS shown in top-left (~25-30 FPS)
- [ ] Press 's' → keypoint vector shape shown (should be 300)
- [ ] Press 'q' → graceful exit

---

## Directory Structure

Ensure these directories exist:

```bash
mkdir -p data/raw data/processed data/labels
mkdir -p models logs
```

Or in PowerShell:
```powershell
@("data/raw", "data/processed", "data/labels", "models", "logs") | ForEach-Object { New-Item -ItemType Directory -Path $_ -Force }
```

---

## Troubleshooting

### **Issue**: ModuleNotFoundError: No module named 'mediapipe'

**Solution**: 
```bash
pip install --upgrade mediapipe
```

### **Issue**: Webcam not detected

**Solution**:
```bash
# List available cameras
python -c "import cv2; print(cv2.getBuildInformation())"

# Or test camera access
python -c "
import cv2
cap = cv2.VideoCapture(0)
print(f'Camera 0: {cap.isOpened()}')
cap = cv2.VideoCapture(1)
print(f'Camera 1: {cap.isOpened()}')
"
```

If no camera is detected, try index 1 or higher:
- Modify `M1_improved.py` line: `cap = cv2.VideoCapture(1)`

### **Issue**: Slow FPS (<15)

**Reasons & Solutions**:
1. Older laptop → reduce frame resolution in M1_improved.py:
   ```python
   cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
   cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
   ```

2. CPU bottleneck → use GPU acceleration (GPU torch installed)

3. Background processes → close other apps

### **Issue**: NaN or zero keypoints

**Solution**: Ensure shoulders are visible to camera (torso in frame)

### **Issue**: Import error for `.task` files

**Solution**: Verify model files exist in current directory:
```bash
ls -la *.task
# or in PowerShell:
Get-ChildItem *.task
```

---

## For GPU Acceleration (Optional)

If you have NVIDIA GPU and CUDA installed:

```bash
# Reinstall PyTorch for GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify GPU
python -c "import torch; print(f'GPU available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name()}')"
```

---

## Development Workflow

### Running M1 (Keypoint Extraction)
```bash
python M1_improved.py
```

### Collecting Data (M2/M3 prep)
```bash
python data_collector.py --label "A" --samples 20
# Records 20 samples of ASL letter "A"
```

### Training Classifier (M2)
```bash
python m2_static_classifier.py --train --data-dir data/processed
```

### Live Testing (M5)
```bash
python m5_live_inference.py --model models/asl_alphabet.pkl
```

---

## FAQ

**Q: Can I use a phone camera instead of webcam?**  
A: Not directly. You'd need to stream the phone's camera via IP camera apps (e.g., IP Webcam on Android), then point OpenCV to that stream.

**Q: Do I need a GPU?**  
A: No, CPU is fine for v1. GPU speeds up training for M4+ but not necessary for M1-M3.

**Q: How much data do I need?**  
A: For M2 (static): 10-20 samples per class (26 letters = 260-520 samples)  
For M4 (dynamic): 20-50 samples per word (50 words = 1000-2500 samples)

**Q: Can I train on other people's data?**  
A: Yes, but model generalization will be limited. Mix your own recordings with public datasets (WLASL, ASL Alphabet) for better results.

**Q: What if lighting is bad?**  
A: MediaPipe is fairly robust to lighting, but ensure your hands/torso are clearly visible. Avoid harsh backlighting.

---

## Next Steps After Setup

1. ✅ Run M1: `python M1_improved.py` → verify keypoint extraction works
2. 🔄 **M2 Prep**: Collect ASL alphabet training data
3. 🔄 **M2**: Train static gesture classifier
4. 📋 **M3**: Collect dynamic sign sequences
5. 📋 **M4**: Train LSTM on temporal sequences

---

## Support & Debugging

- **Keypoint shape**: Press 's' in M1 to inspect (should be 300)
- **Model accuracy**: Check `logs/` after training
- **Real-time performance**: Monitor FPS in top-left of video
- **Errors**: Run with verbose flag: `python M1_improved.py 2>&1 | tee debug.log`

---

**Status**: Setup complete, M1 ready to run

Last updated: 2026-07-14
