# EchoSign - Quick Start Guide

Get up and running in 5 minutes.

## 1. Install Dependencies

```bash
pip install opencv-python mediapipe numpy scikit-learn torch
```

## 2. Verify M1 (Keypoint Extraction)

```bash
python M1_improved.py
```

You should see:
- ✅ Webcam opens with skeleton overlay
- ✅ FPS counter in top-left (~25-30 FPS)
- ✅ Green skeleton (pose), cyan/yellow (hands)

**Controls**:
- `s` - Print keypoint vector info
- `SPACE` - Pause/resume
- `q` - Quit

## 3. Collect Training Data for M2 (ASL Alphabet)

Record 20 samples of letter "A":

```bash
python data_collector.py --label A --samples 20
```

This will:
1. Open your webcam
2. Wait for you to press SPACE
3. Record 1.5 seconds of keypoint data
4. Save to `data/raw/A_*.npy`

**Repeat for all 26 letters** (A-Z) or at least 5-10 for testing:

```bash
for letter in B C D E F; do
  python data_collector.py --label $letter --samples 10
done
```

Or on PowerShell:
```powershell
"B","C","D","E","F" | ForEach-Object {
  python data_collector.py --label $_ --samples 10
}
```

## 4. Review Collected Data

```bash
python data_collector.py --review
```

Shows total samples and frames collected.

## 5. Train M2 Static Classifier

```bash
python m2_static_classifier.py --train
```

This will:
1. Load all `.npy` files from `data/raw/`
2. Extract frame features
3. Train a Random Forest on 80% of data
4. Test on 20% held-out set
5. Print accuracy + confusion matrix
6. Save model to `models/asl_alphabet.pkl`

## Next Steps

| Step | Command | Status |
|------|---------|--------|
| 1. Setup | `pip install ...` | ✅ Ready |
| 2. Verify M1 | `python M1_improved.py` | ✅ Ready |
| 3. Collect data | `python data_collector.py --label A` | ✅ Ready |
| 4. Train M2 | `python m2_static_classifier.py --train` | ✅ Ready |
| 5. Live test | `python m5_live_inference.py` | 🔄 After M4 |

## Troubleshooting

**Webcam not found?**
```bash
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```

Try indices 1, 2, etc. if 0 doesn't work. Edit `M1_improved.py`:
```python
cap = cv2.VideoCapture(1)  # Change 0 to 1, 2, ...
```

**ModuleNotFoundError?**
```bash
pip install --upgrade mediapipe opencv-python
```

**Slow FPS?**
Reduce resolution in M1_improved.py:
```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
```

## Key Files

| File | Purpose |
|------|---------|
| `M1_improved.py` | Real-time keypoint extraction & visualization |
| `data_collector.py` | Record training data with labels |
| `m2_static_classifier.py` | Train & evaluate ASL alphabet classifier |
| `README.md` | Full project overview |
| `SETUP.md` | Detailed installation guide |

## Recommended Workflow for First Time

1. **10 min**: Install deps + run M1
2. **30 min**: Collect data for 3-5 letters
3. **5 min**: Review collected data
4. **5 min**: Train M2 classifier
5. **See results**: Check accuracy on your data

Total: ~50 minutes for a working end-to-end pipeline.

---

**Questions?** Check `README.md` for full documentation or `M1_VERIFICATION_REPORT.md` for technical details.
