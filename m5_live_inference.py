"""
M5 -- Real-Time Inference Pipeline
====================================
Integrates M1 (keypoint extraction), M4 (sequence model), and post-processing
into a live transcription system

Pipeline:
    Webcam → M1 (keypoints) → Buffer → M4 (inference) → Post-process → Output

Post-processing:
    - Confidence thresholding (only high-confidence predictions)
    - Temporal smoothing (majority vote over K frames)
    - Debounce (require N stable frames before committing)
    - Idle detection (filter out no-sign periods)

Usage:
    python m5_live_inference.py --model models/sequence_model.pt
"""

import cv2
import numpy as np
import torch
from pathlib import Path
from collections import deque
import time
import argparse
from typing import Tuple, Optional

import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker, HandLandmarkerOptions,
    PoseLandmarker, PoseLandmarkerOptions,
    RunningMode,
)

# Import M1 utilities
from M1_improved import extract_keypoints, normalize_keypoints

# Import M4 model
try:
    from m4_sequence_model import SequenceModel
except:
    SequenceModel = None

# Configuration
CONFIG = {
    "hand_model": "hand_landmarker.task",
    "pose_model": "pose_landmarker.task",
    "sequence_length": 45,  # frames to buffer
    "confidence_threshold": 0.7,
    "smoothing_window": 5,  # frames for majority voting
    "debounce_frames": 3,  # require 3 stable predictions
    "fps": 30,
}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
]


class PostProcessor:
    """Post-processing for predictions (smoothing, debounce, etc)."""

    def __init__(self, smoothing_window: int = 5, debounce_frames: int = 3):
        self.smoothing_window = smoothing_window
        self.debounce_frames = debounce_frames
        self.prediction_history = deque(maxlen=smoothing_window)
        self.confidence_history = deque(maxlen=smoothing_window)
        self.committed_predictions = deque(maxlen=100)

    def process(self, prediction: str, confidence: float) -> Optional[Tuple[str, float]]:
        """
        Process prediction with smoothing and debounce.
        Returns (word, confidence) or None if not stable yet.
        """
        self.prediction_history.append(prediction)
        self.confidence_history.append(confidence)

        # Apply temporal smoothing (majority vote)
        if len(self.prediction_history) >= self.smoothing_window:
            from collections import Counter
            pred_counts = Counter(self.prediction_history)
            smoothed_pred, count = pred_counts.most_common(1)[0]
            smoothed_conf = np.mean(list(self.confidence_history))

            # Apply debounce (require stable predictions)
            if count >= self.debounce_frames:
                # Check if different from last committed
                if (not self.committed_predictions or
                    self.committed_predictions[-1] != smoothed_pred):
                    self.committed_predictions.append(smoothed_pred)
                    return smoothed_pred, smoothed_conf

        return None


class LiveInferenceEngine:
    """Real-time inference with keypoint extraction + sequence model."""

    def __init__(self, model_path: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load M1 models
        self.hand_options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=CONFIG["hand_model"]),
            running_mode=RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.pose_options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=CONFIG["pose_model"]),
            running_mode=RunningMode.VIDEO,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Load M4 model if provided
        self.model = None
        self.label_encoder = None
        if model_path and Path(model_path).exists():
            self.load_model(model_path)

        # Buffers
        self.keypoint_buffer = deque(maxlen=CONFIG["sequence_length"])
        self.post_processor = PostProcessor(
            smoothing_window=CONFIG["smoothing_window"],
            debounce_frames=CONFIG["debounce_frames"]
        )

    def load_model(self, model_path: str):
        """Load trained sequence model."""
        if SequenceModel is None:
            print("PyTorch not available")
            return

        self.model = SequenceModel(num_classes=26).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()
        print(f"✓ Model loaded from {model_path}")

    def predict_sequence(self) -> Tuple[Optional[str], float]:
        """Infer on buffered keypoint sequence."""
        if not self.model or len(self.keypoint_buffer) < 10:
            return None, 0.0

        # Pad to fixed length
        seq = np.array(list(self.keypoint_buffer))
        seq_len = len(seq)

        if seq_len < CONFIG["sequence_length"]:
            seq = np.pad(seq, ((0, CONFIG["sequence_length"] - seq_len), (0, 0)))
        else:
            seq = seq[:CONFIG["sequence_length"]]

        # Inference
        with torch.no_grad():
            x = torch.FloatTensor(seq).unsqueeze(0).to(self.device)  # [1, seq_len, 300]
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)[0]
            conf, pred_idx = probs.max(dim=0)

            # Map to class name (A-Z for now)
            pred_char = chr(ord('A') + pred_idx.item())
            return pred_char, conf.item()

        return None, 0.0

    def run(self):
        """Main inference loop."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("ERROR: Could not open webcam")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        start_time = time.time()
        fps_history = deque(maxlen=10)
        prev_time = 0
        transcript = []

        print("\n" + "="*60)
        print("EchoSign M5 - Real-Time Inference Pipeline")
        print("="*60)
        print("Controls:")
        print("  q     - Quit")
        print("  SPACE - Pause/Resume")
        print("  c     - Clear transcript")
        print("="*60 + "\n")

        paused = False

        with HandLandmarker.create_from_options(self.hand_options) as hand_landmarker, \
             PoseLandmarker.create_from_options(self.pose_options) as pose_landmarker:

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]

                if not paused:
                    # Extract keypoints
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                    timestamp_ms = int((time.time() - start_time) * 1000)

                    hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
                    pose_result = pose_landmarker.detect_for_video(mp_image, timestamp_ms)

                    # Extract and normalize
                    kp = extract_keypoints(hand_result, pose_result)
                    kp_norm = normalize_keypoints(kp)
                    self.keypoint_buffer.append(kp_norm)

                    # Draw landmarks
                    self._draw_landmarks(frame, hand_result, pose_result)

                    # Predict
                    if len(self.keypoint_buffer) >= 10:
                        pred, conf = self.predict_sequence()
                        if pred and conf > CONFIG["confidence_threshold"]:
                            result = self.post_processor.process(pred, conf)
                            if result:
                                word, avg_conf = result
                                transcript.append(word)
                                print(f"🎯 Recognized: {word} ({avg_conf:.2f})")

                    # FPS
                    curr_time = time.time()
                    if prev_time > 0:
                        fps = 1.0 / (curr_time - prev_time)
                        fps_history.append(fps)
                    prev_time = curr_time
                    avg_fps = np.mean(fps_history) if fps_history else 0

                else:
                    avg_fps = 0

                # Draw HUD
                self._draw_hud(frame, avg_fps, len(self.keypoint_buffer), transcript)

                cv2.imshow("EchoSign M5 - Real-Time Inference (q=quit, SPACE=pause, c=clear)", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n✓ Exiting...")
                    break
                elif key == ord(' '):
                    paused = not paused
                    print(f"\n>>> {'PAUSED' if paused else 'RESUMED'}")
                elif key == ord('c'):
                    transcript = []
                    print("\n>>> Transcript cleared")

        cap.release()
        cv2.destroyAllWindows()

        # Print final transcript
        print("\n" + "="*60)
        print("Final Transcript:")
        print(" ".join(transcript) if transcript else "(empty)")
        print("="*60)

    def _draw_landmarks(self, frame, hand_result, pose_result):
        """Draw skeleton overlay."""
        h, w = frame.shape[:2]

        # Draw pose
        if pose_result.pose_landmarks:
            pose_landmarks = pose_result.pose_landmarks[0]
            for start_idx, end_idx in POSE_CONNECTIONS:
                start = pose_landmarks[start_idx]
                end = pose_landmarks[end_idx]
                start_pos = (int(start.x * w), int(start.y * h))
                end_pos = (int(end.x * w), int(end.y * h))
                cv2.line(frame, start_pos, end_pos, (0, 255, 0), 2)

            for landmark in pose_landmarks:
                pos = (int(landmark.x * w), int(landmark.y * h))
                cv2.circle(frame, pos, 4, (0, 255, 0), -1)

        # Draw hands
        if hand_result.hand_landmarks:
            for hand_landmarks, handedness in zip(hand_result.hand_landmarks,
                                                  hand_result.handedness):
                color = (255, 255, 0) if handedness[0].category_name == "Right" else (255, 0, 255)

                for start_idx, end_idx in HAND_CONNECTIONS:
                    start = hand_landmarks[start_idx]
                    end = hand_landmarks[end_idx]
                    start_pos = (int(start.x * w), int(start.y * h))
                    end_pos = (int(end.x * w), int(end.y * h))
                    cv2.line(frame, start_pos, end_pos, color, 1)

                for landmark in hand_landmarks:
                    pos = (int(landmark.x * w), int(landmark.y * h))
                    cv2.circle(frame, pos, 3, color, -1)

    def _draw_hud(self, frame, fps, buffer_len, transcript):
        """Draw heads-up display."""
        h, w = frame.shape[:2]

        # FPS
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Buffer status
        buffer_pct = min(100, int(100 * buffer_len / CONFIG["sequence_length"]))
        cv2.putText(frame, f"Buffer: {buffer_pct}%", (10, 65),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Transcript
        transcript_text = " ".join(transcript[-10:]) if transcript else "(waiting...)"
        cv2.putText(frame, f"Transcript: {transcript_text}", (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)


def main():
    parser = argparse.ArgumentParser(description="M5: Real-Time Inference")
    parser.add_argument("--model", default="models/sequence_model.pt",
                       help="Path to trained model")
    args = parser.parse_args()

    engine = LiveInferenceEngine(model_path=args.model)
    engine.run()


if __name__ == "__main__":
    main()
