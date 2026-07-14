# EchoSign - Project Status & Checklist

**Project**: Real-Time Sign Language Translator  
**Start Date**: 2026-07-14  
**Target**: v1 Portfolio Demo (ASL alphabet + 20-50 dynamic words)

---

## Milestone Status

### M1 - Keypoint Pipeline ✅ COMPLETE

**Status**: VERIFIED & PRODUCTION-READY

- [x] Real-time webcam capture (30 FPS)
- [x] MediaPipe hand + pose landmark extraction
- [x] 300D fixed-size keypoint vector
- [x] Shoulder-relative normalization (all axes)
- [x] Real-time skeleton visualization
- [x] FPS monitoring and status display
- [x] Robust handling of missing landmarks
- [x] Comprehensive documentation

**Deliverables**:
- `M1_improved.py` - Enhanced implementation ✅
- `M1_VERIFICATION_REPORT.md` - Detailed findings ✅
- Model files: `hand_landmarker.task`, `pose_landmarker.task` ✅

**Known Limitations**:
- Single-signer training data (will need self-recording)
- No multi-hand disambiguation (assumes at most 2 hands)
- Lighting-dependent accuracy (MediaPipe can struggle in low light)

**Next**: Use M1 to collect training data for M2

---

### M2 - Static Gesture MVP 🔄 READY

**Status**: SKELETON READY, AWAITING DATA

- [ ] Implement handcrafted feature extraction
- [ ] Train Random Forest baseline on frame-wise features
- [ ] Evaluate accuracy on 26-letter ASL alphabet
- [ ] Integrate confidence thresholding
- [ ] Test on held-out set (>85% target)

**Deliverables**:
- `m2_static_classifier.py` - Classifier skeleton ✅
- `data_collector.py` - Data collection utility ✅
- Training data: `data/processed/{A..Z}_train.npy`
- Trained model: `models/asl_alphabet.pkl`

**Prerequisites**:
- [ ] Collect ~20 samples per letter (26 letters = 520 samples minimum)
- [ ] Save to `data/raw/` as `.npy` files

**Key Decision**: Should we augment with public datasets (WLASL, ASL Alphabet) or pure self-recording?
- **Recommendation**: Start with pure self-recording for simplicity, add public data in M3 if needed

**Success Criteria**: >85% accuracy on held-out test set

---

### M3 - Dynamic Sign Data Collection 📋 PLANNED

**Status**: NOT STARTED

- [ ] Define vocabulary (20-50 words/phrases)
- [ ] Record temporal sequences for each word
- [ ] Label and organize by session
- [ ] Create train/val/test splits by session (avoid leakage)

**Deliverables**:
- Temporal keypoint sequences: `data/processed/{WORD}_{i}.npy`
- Label definitions: `data/labels/dynamic_vocab.json`
- Dataset splits: `data/processed/train.pkl`, `test.pkl`

**Key Decision**: Which sign language and vocabulary?
- **Recommendation**: ASL (most public data), vocabulary = common courtesy signs (hello, thank you, yes, no, please, help, good, bad, food, water, etc.)

**Success Criteria**: 500-1000 sequences collected across vocabulary

---

### M4 - Sequence Model 📋 PLANNED

**Status**: NOT STARTED

- [ ] Implement LSTM/GRU architecture
- [ ] Train on temporal keypoint sequences
- [ ] Evaluate latency (<300ms per inference)
- [ ] Evaluate accuracy (>85% target)
- [ ] Compare vs baselines (CNN+LSTM, Transformer)

**Deliverables**:
- `m4_sequence_model.py` - LSTM trainer & evaluator
- Trained model: `models/sequence_model.pt`
- Training logs: `logs/m4_training.csv`

**Architecture (baseline)**:
```
Input: [batch, seq_len, 300]
  ↓
LSTM(128, num_layers=2, dropout=0.2)
  ↓
Dense(vocab_size + 1)
  ↓
Output: logits for each class + "idle"
```

**Success Criteria**: >85% accuracy, <300ms latency

---

### M5 - Real-Time Integration 📋 PLANNED

**Status**: NOT STARTED

- [ ] Integrate M1 (keypoint extraction)
- [ ] Implement keypoint buffering (sliding window)
- [ ] Plug in M4 model for inference
- [ ] Add post-processing: confidence thresholding, temporal smoothing, debounce
- [ ] Display live predictions and confidence

**Deliverables**:
- `m5_live_inference.py` - Live inference pipeline
- Real-time transcript with confidence scores

**Success Criteria**: Smooth, responsive predictions without hallucinations

---

### M6 - Output Layer & UI 📋 PLANNED

**Status**: NOT STARTED

- [ ] Streamlit UI with video + predictions
- [ ] Running transcript display
- [ ] Text-to-speech (pyttsx3)
- [ ] Demo video recording
- [ ] Visual feedback (landmarks + confidence overlay)

**Deliverables**:
- `m6_demo_ui.py` - Streamlit app
- Shareable UI link (or standalone executable)

---

### M7 - Browser Deployment 🎯 STRETCH

**Status**: NOT STARTED

- [ ] Convert M4 model to TensorFlow.js
- [ ] Build web UI (HTML + vanilla JS or React)
- [ ] Deploy to Vercel/GitHub Pages/Streamlit Cloud
- [ ] Test in live interview setting

**Deliverables**:
- `app.html` + supporting files
- Shareable web link

---

## Project Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Keypoint latency | <300ms | ✅ ~30-50ms |
| Model accuracy (vocab) | >85% | 🔄 Pending M2 |
| False-positive rate (idle) | <5% | 🔄 Pending M5 |
| Inference latency | <100ms | 🔄 Pending M4 |
| Live demo smoothness | 25+ FPS | ✅ M1 achieves 28-30 |

---

## Data Collection Plan

### Phase 1: ASL Alphabet (M2)
- **Scope**: 26 letters (A-Z)
- **Samples per letter**: 20 (total 520)
- **Duration per sample**: 1.5 seconds
- **Estimated collection time**: 2-3 hours
- **Status**: Ready to start with `data_collector.py`

### Phase 2: Common Words (M3)
- **Scope**: 50 common ASL words/phrases
- **Samples per word**: 20 (total 1000)
- **Duration per sample**: 1.5-3 seconds
- **Estimated collection time**: 8-10 hours
- **Status**: Planned after M2

---

## Development Workflow

### Current Sprint (M2)

1. **Collect data** (2-3 hours)
   ```bash
   for letter in {A..Z}; do
     python data_collector.py --label $letter --samples 20
   done
   ```

2. **Train classifier** (5-10 minutes)
   ```bash
   python m2_static_classifier.py --train
   ```

3. **Evaluate** (2 minutes)
   ```bash
   python m2_static_classifier.py --evaluate
   ```

4. **Iterate** if accuracy <85%
   - Collect more samples
   - Adjust feature extraction
   - Try different classifier hyperparams

### Testing Strategy

- **M1**: Manual - visually verify skeleton overlay
- **M2**: Unit test - accuracy on validation set
- **M3**: Manual - verify label annotations
- **M4**: Unit test - accuracy + latency benchmarks
- **M5**: Integration test - end-to-end live demo
- **M6**: User test - demo with audience

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data scarcity | M2/M4 won't generalize | Collect 20+ samples per class |
| Class imbalance (idle > signing) | False positives | Explicit "idle" class + threshold tuning |
| Single-signer overfitting | Won't work for other signers | Explicitly note limitation in demo |
| Lighting variance | Detection fails | Collect data in multiple lighting conditions |
| Latency (buffer + model) | >300ms | Monitor each stage, optimize bottleneck |

---

## File Structure

```
V:\EchoSign/
├── M1_improved.py              ✅ Complete
├── M1.py                       (reference)
├── M1_VERIFICATION_REPORT.md   ✅ Complete
├── data_collector.py           ✅ Complete
├── m2_static_classifier.py     ✅ Skeleton
├── m4_sequence_model.py        ✅ Skeleton
├── README.md                   ✅ Complete
├── SETUP.md                    ✅ Complete
├── QUICKSTART.md               ✅ Complete
├── PROJECT_STATUS.md           ✅ This file
│
├── data/
│   ├── raw/                    (training data - empty)
│   ├── processed/              (train/val/test splits)
│   └── labels/
│       └── asl_alphabet.json   ✅ Complete
├── models/                     (trained models - empty)
├── logs/                       (training logs - empty)
│
├── hand_landmarker.task        (7.5MB model)
└── pose_landmarker.task        (30MB model)
```

---

## Quick Links

- **Setup**: `SETUP.md` - Installation & environment
- **Quick Start**: `QUICKSTART.md` - Get running in 5 min
- **Documentation**: `README.md` - Full project overview
- **M1 Details**: `M1_VERIFICATION_REPORT.md` - Technical findings
- **PRD**: `EchoSign_PRD.md` - Product requirements

---

## Next Steps (Immediate)

1. ✅ M1 verified and improved
2. 🔄 **M2 Ready**: Start collecting ASL alphabet data
3. 🔄 **M2 Ready**: Train static classifier baseline
4. 📋 **M3 Planned**: Collect dynamic sign vocabulary
5. 📋 **M4 Planned**: Train LSTM on sequences
6. 📋 **M5 Planned**: Real-time integration
7. 📋 **M6 Planned**: UI & output layer

---

**Last Updated**: 2026-07-14  
**Status**: M1 ✅ COMPLETE | M2 🔄 READY TO START
