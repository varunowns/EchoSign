# PRD: Real-Time Sign Language Translator

## 1. Overview

**Product**: A real-time system that captures webcam video, tracks hand/body/face keypoints using a pose-estimation model, and classifies the resulting keypoint sequences into sign language gestures — outputting text and optionally speech.

**Problem**: Deaf and hard-of-hearing individuals face communication barriers with people who don't know sign language. Existing solutions are either expensive (dedicated hardware), offline (video-only translation apps with no real-time feedback), or limited to static alphabet recognition (no continuous/dynamic signs).

**Target user (v1)**: Solo demo/portfolio project simulating an assistive tool — designed for live interview demos and as a foundation that could grow into a real accessibility product.

**Success definition for v1**: A working end-to-end pipeline that recognizes a limited vocabulary (e.g., ASL alphabet + ~20-50 common words/phrases) from live webcam input with acceptable latency (<300ms) and reasonable accuracy (>85% on the trained vocabulary).

---

## 2. Goals & Non-Goals

### Goals
- Real-time keypoint extraction from webcam (hands, pose, optionally face).
- Temporal sequence classification to distinguish dynamic signs (not just static hand shapes).
- Live text output; optional text-to-speech.
- Demoable end-to-end in a browser or lightweight desktop app.
- Clean, modular architecture that separates capture → keypoint extraction → classification → output, so each piece can be swapped/improved independently.

### Non-Goals (v1)
- Full ASL/BSL grammar understanding (facial grammar, classifiers, spatial referencing) — out of scope initially.
- Multi-signer, multi-language support.
- Production-grade accessibility certification.
- Mobile app deployment (desktop/browser only for v1).

---

## 3. System Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌───────────────┐
│   Webcam    │────▶│  Pose Estimation  │────▶│  Keypoint Buffer   │────▶│  Sequence Model  │────▶│  Text / Speech │
│   Capture   │     │ (MediaPipe Holistic)│    │ (sliding window)   │     │ (LSTM/GRU/Trans.)│     │     Output     │
└─────────────┘     └──────────────────┘     └───────────────────┘     └─────────────────┘     └───────────────┘
                                                                                  │
                                                                                  ▼
                                                                         ┌─────────────────┐
                                                                         │ Confidence /     │
                                                                         │ Smoothing Layer  │
                                                                         └─────────────────┘
```

### Step-by-step pipeline

1. **Video Capture**
   - Input: webcam stream (30 FPS target).
   - Frame preprocessing: resize, normalize, optional mirror.

2. **Keypoint Extraction (Pose Estimation)**
   - Use **MediaPipe Holistic** (recommended over OpenPose for real-time CPU/browser use — lighter, gives hands + pose + face landmarks in one pass).
   - Extract per frame:
     - 21 landmarks per hand × 2 hands (x, y, z)
     - 33 pose landmarks (upper body focus)
     - Optionally 468 face landmarks (only if doing facial-grammar-aware signs later — skip in v1)
   - Normalize landmarks relative to a stable reference point (e.g., shoulder midpoint) and scale by shoulder width, to make the model invariant to distance-from-camera and body size.

3. **Keypoint Buffering (Temporal Window)**
   - Maintain a rolling buffer of the last N frames (e.g., 30–45 frames ≈ 1–1.5 sec at 30fps).
   - Handle missing/occluded landmarks (interpolate or zero-fill).
   - This buffer is the input unit fed to the sequence model — this is what makes dynamic signs (not just static letters) possible.

4. **Sequence Classification**
   - Model options (pick one for v1, note others as future work):
     - **LSTM/GRU** over the keypoint sequence — simplest, good baseline, fast to train.
     - **1D-CNN + LSTM hybrid** — CNN extracts spatial patterns per frame, LSTM models temporal dynamics.
     - **Transformer encoder** — better for longer-range dependencies, more data-hungry.
   - Output: probability distribution over vocabulary classes (+ a "no sign / idle" class — important for continuous streaming).

5. **Post-processing / Smoothing**
   - Confidence thresholding (reject low-confidence predictions).
   - Temporal smoothing (majority vote or exponential smoothing over last K predictions) to avoid flickering/jittery output.
   - Debounce: require a sign to be "held" or stable for M consecutive frames before committing it as recognized (prevents mid-transition frames from firing false positives).

6. **Output Layer**
   - Text: append recognized sign/word to a running transcript, shown live on screen.
   - Speech (optional): Text-to-speech (browser Web Speech API or a Python TTS lib) reads out committed words.
   - Visual feedback: overlay skeleton/hand landmarks on video feed + current prediction + confidence score (great for live demo).

---

## 4. Data & Vocabulary Strategy

- **v1 vocabulary scope**: Start small and provably correct — e.g., ASL fingerspelling alphabet (26 static classes, easiest to validate) → then add 20–50 common dynamic words/phrases (hello, thank you, yes, no, please, help, etc.).
- **Data sources**:
  - Public datasets: WLASL (Word-Level ASL), ASL Alphabet dataset (Kaggle), MS-ASL, INCLUDE (Indian Sign Language) — pick based on which sign language you're targeting.
  - Self-recorded data: record yourself signing each class multiple times under varied lighting/angles — often necessary since public datasets may not match your webcam/setup distribution.
- **Data format**: store extracted keypoints (not raw video) as the training dataset — much smaller, faster to iterate, and removes background/lighting as a confound.
- **Train/val/test split**: split by *recording session*, not by frame, to avoid leakage (same session frames are highly correlated).

---

## 5. Tech Stack

| Layer | Tool |
|---|---|
| Pose estimation | MediaPipe Holistic (Python or JS/Web) |
| Sequence model | PyTorch or TensorFlow/Keras (LSTM/GRU baseline) |
| Real-time app | Python + OpenCV (desktop demo) OR MediaPipe.js + TensorFlow.js (browser demo — better for live interview sharing) |
| Speech output | pyttsx3 (Python) or Web Speech API (browser) |
| Experiment tracking | Weights & Biases or simple CSV logging |
| Deployment (stretch) | Streamlit/Gradio for a shareable demo UI |

**Recommendation**: build the core pipeline in Python first (faster iteration for model training), then port the trained model to a browser demo (TensorFlow.js) for a polished, link-shareable interview artifact.

---

## 6. Evaluation Metrics

- **Classification accuracy** on held-out vocabulary (per-class + overall).
- **Latency**: end-to-end time from frame capture to prediction (target <300ms for "real-time" feel).
- **False-positive rate on idle/no-sign** frames — critical for a good live demo (don't want it hallucinating words when you're not signing).
- **Robustness**: accuracy under different lighting, camera distance, and signer (if testing with more than yourself).

---

## 7. Milestones (suggested build order)

1. **M1 — Keypoint pipeline**: Webcam → MediaPipe → visualize landmarks in real time. (Proves capture + extraction works.)
2. **M2 — Static gesture MVP**: Classify single-frame hand shapes (ASL alphabet) with a simple classifier (even a random forest on keypoint features works here). Validates the whole loop end-to-end on the easy case.
3. **M3 — Data collection for dynamic signs**: Record + label keypoint sequences for chosen word vocabulary.
4. **M4 — Sequence model**: Train LSTM/GRU on buffered sequences; evaluate offline on held-out clips.
5. **M5 — Real-time integration**: Plug trained model into the live pipeline with smoothing/debounce logic.
6. **M6 — Output layer + polish**: Add text overlay, TTS, confidence display, demo UI.
7. **M7 (stretch) — Browser deployment**: Port to TensorFlow.js for a shareable web demo.

---

## 8. Risks & Open Questions

- **Data scarcity**: dynamic-sign datasets are much smaller than static-image datasets — may need significant self-recording.
- **Class imbalance / idle detection**: most of any real video stream is "not signing" — the idle class needs real attention or the model will over-fire.
- **Generalization**: a model trained on your own recordings may not generalize to other signers' body proportions/signing speed — worth explicitly noting as a limitation in the demo narrative rather than overclaiming.
- **Which sign language to target**: ASL has the most public data/tooling; worth confirming this is the intended target before data collection starts.
- **Scope creep**: facial grammar and full grammatical structure are real parts of sign languages but are a much bigger research problem — keep v1 scoped to vocabulary-level recognition and say so explicitly in any demo/writeup.

---

## 9. Demo Narrative (for interviews)

Live webcam feed → skeleton overlay → signs performed → text appears live → optionally spoken aloud. Narrate the pipeline stages while demoing (capture → keypoints → temporal model → smoothing → output) to show the CV + sequence-modeling depth, and close with the accessibility framing and known limitations (vocabulary size, single-signer training data) to show maturity/self-awareness about scope.
