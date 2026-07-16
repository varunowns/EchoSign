"""
M5 -- Real-Time Inference Pipeline
====================================
Integrates M1 (keypoint extraction), M2 (static classifier), and post-processing
into a live transcription system

Pipeline:
    Webcam → M1 (keypoints) → M2 (frame classifier) → Post-process → Output

Post-processing:
    - Confidence thresholding (only high-confidence predictions)
    - Temporal smoothing (majority vote over K frames)
    - Debounce (require N stable frames before committing)

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
import sys
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


BASE_DIR = Path(__file__).resolve().parent


def resolve_asset_path(asset_name: str) -> str:
    """Resolve model assets whether the API runs from repo root or backend/."""
    candidates = [
        BASE_DIR / asset_name,
        BASE_DIR.parent / asset_name,
        BASE_DIR / "backend" / asset_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(BASE_DIR / asset_name)

# Configuration
CONFIG = {
    "hand_model": resolve_asset_path("hand_landmarker.task"),
    "pose_model": resolve_asset_path("pose_landmarker.task"),
    "sequence_length": 45,
    "confidence_threshold": 0.30,
    "smoothing_window": 4,
    "debounce_frames": 2,
    "fps": 30,
}


class PostProcessor:
    """Post-processing for predictions (smoothing, debounce, etc).

    Tracks predictions over a sliding window and only commits when
    the same prediction appears N+ times in a window of size K.
    """

    def __init__(self, smoothing_window: int = 5, debounce_frames: int = 3):
        self.smoothing_window = smoothing_window
        self.debounce_frames = debounce_frames
        self.prediction_history = deque(maxlen=smoothing_window)
        self.confidence_history = deque(maxlen=smoothing_window)
        self.last_committed = None

    def reset(self):
        """Clears all history. Call on WebSocket reconnect."""
        self.prediction_history.clear()
        self.confidence_history.clear()
        self.last_committed = None

    def process(self, prediction: str, confidence: float) -> Optional[Tuple[str, float]]:
        """
        Returns (word, confidence) or None if not stable yet.
        Uses majority-vote smoothing + debounce.
        """
        self.prediction_history.append(prediction)
        self.confidence_history.append(confidence)

        if len(self.prediction_history) < self.smoothing_window:
            return None  # not enough data yet

        from collections import Counter
        pred_counts = Counter(self.prediction_history)
        smoothed_pred, count = pred_counts.most_common(1)[0]
        smoothed_conf = float(np.mean(list(self.confidence_history)))

        # Debounce: require N stable frames within the window
        if count < self.debounce_frames:
            return None

        # Only commit if different from last committed
        if self.last_committed == smoothed_pred:
            return None

        self.last_committed = smoothed_pred
        return smoothed_pred, smoothed_conf


class LiveInferenceEngine:
    """Real-time inference with keypoint extraction + M2 frame classifier."""

    def __init__(self, model_path: Optional[str] = None, m2_classifier=None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.m2_classifier = m2_classifier  # Static frame classifier (M2) — PRIMARY

        # Load M1 models
        self.hand_options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=CONFIG["hand_model"]),
            running_mode=RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        self.pose_options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=CONFIG["pose_model"]),
            running_mode=RunningMode.VIDEO,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Load M4 model if provided (secondary/fallback)
        self.model = None
        self.label_encoder = None
        if model_path and Path(model_path).exists():
            self.load_model(model_path)

        # Create MediaPipe instances
        self.hand_landmarker = HandLandmarker.create_from_options(self.hand_options)
        self.pose_landmarker = PoseLandmarker.create_from_options(self.pose_options)

        # Monotonic timestamp counter for MediaPipe VIDEO mode
        # (must always increase, even across reset() calls)
        self._mediapipe_timestamp = 0
        self._timestamp_step_ms = 33  # ~30 FPS

        # M2 gets its OWN post-processor (separate from M4)
        self.m2_post_processor = PostProcessor(
            smoothing_window=CONFIG["smoothing_window"],
            debounce_frames=CONFIG["debounce_frames"]
        )

        # Initialize all mutable state
        self.reset()

    def reset(self):
        """Reset all per-session state. Call on WebSocket (re)connect."""
        self.keypoint_buffer = deque(maxlen=CONFIG["sequence_length"])
        self.start_time = time.time()
        self.prev_time = 0.0
        self.fps_history = deque(maxlen=10)
        self.frame_counter = 0
        self.m2_post_processor.reset()
        print("[RESET] Engine state cleared for new session", flush=True)

    def load_model(self, model_path: str):
        """Load trained sequence model."""
        if SequenceModel is None:
            print("PyTorch not available")
            return

        checkpoint = torch.load(model_path, map_location=self.device)
        fc_weight = checkpoint.get('fc.weight')
        if fc_weight is not None:
            num_classes = fc_weight.shape[0]
        else:
            num_classes = 26

        self.model = SequenceModel(num_classes=num_classes).to(self.device)
        self.model.load_state_dict(checkpoint)
        self.model.eval()
        print(f"[OK] Model loaded from {model_path} (num_classes={num_classes})")

    def _extract_keypoints(self, frame):
        """Run MediaPipe and return keypoints."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Use monotonic timestamp that always increases (MediaPipe VIDEO mode requirement)
        self._mediapipe_timestamp += self._timestamp_step_ms
        timestamp_ms = self._mediapipe_timestamp

        hand_result = self.hand_landmarker.detect_for_video(mp_image, timestamp_ms)
        pose_result = self.pose_landmarker.detect_for_video(mp_image, timestamp_ms)

        kp = extract_keypoints(hand_result, pose_result)
        kp_norm = normalize_keypoints(kp)
        self.keypoint_buffer.append(kp_norm)
        self.frame_counter += 1

        # Debug: frame quality (every 200 frames)
        if self.frame_counter % 200 == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            print(f"[DEBUG] Frame #{self.frame_counter}: brightness={gray.mean():.1f}, "
                  f"contrast={gray.std():.1f}", flush=True)

        # Debug: hand detection (every 30 frames)
        has_hands = hand_result and len(hand_result.hand_landmarks) > 0
        if self.frame_counter % 30 == 0:
            if not has_hands:
                print(f"[DEBUG] Frame #{self.frame_counter}: NO hands detected", flush=True)
            else:
                scores = [h[0].score for h in hand_result.handedness]
                print(f"[DEBUG] Frame #{self.frame_counter}: {len(hand_result.hand_landmarks)} hand(s), "
                      f"scores={scores}", flush=True)

        return hand_result, pose_result, has_hands

    def _predict_m2(self) -> Tuple[Optional[str], float]:
        """Run M2 frame classifier on the latest keypoint."""
        if self.m2_classifier is None or len(self.keypoint_buffer) == 0:
            return None, 0.0
        try:
            latest_kp = self.keypoint_buffer[-1]
            pred, conf = self.m2_classifier.predict(latest_kp)
            if self.frame_counter % 10 == 0:
                print(f"[M2] Frame #{self.frame_counter}: pred={pred}, conf={conf:.4f}", flush=True)
            return pred, conf
        except Exception as e:
            print(f"[M2 ERROR] {e}", flush=True)
            return None, 0.0

    def process_frame(self, frame, mirror_input=False):
        """Process a frame and return a WebSocket-friendly payload.

        Primary classifier: M2 (frame-by-frame Random Forest, trained on real data).
        Falls back to M4 (LSTM sequence) if M2 unavailable.
        """
        start = time.perf_counter()

        if mirror_input:
            frame = cv2.flip(frame, 1)
        if frame is None:
            return {"type": "error", "error": "Null frame"}

        # Step 1: Extract keypoints via MediaPipe
        hand_result, pose_result, has_hands = self._extract_keypoints(frame)

        # Step 2: Compute latency and FPS
        curr_time = time.time()
        if self.prev_time > 0:
            self.fps_history.append(1.0 / max(curr_time - self.prev_time, 1e-6))
        self.prev_time = curr_time
        avg_fps = float(np.mean(self.fps_history)) if self.fps_history else 0.0
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Step 3: Build base response
        response = {
            "type": "processing",
            "status": "processing",
            "prediction": None,
            "confidence": None,
            "latency_ms": latency_ms,
            "fps": round(avg_fps, 2),
            "buffer_fill": len(self.keypoint_buffer),
            "has_hands": has_hands,
            "has_pose": pose_result is not None and len(pose_result.pose_landmarks) > 0,
        }

        # Step 4: Run M2 classifier (PRIMARY — real ASL alphabet data)
        if self.m2_classifier is not None and has_hands:
            m2_pred, m2_conf = self._predict_m2()
            response["m2_prediction"] = m2_pred
            response["m2_confidence"] = round(m2_conf, 4)

            if m2_pred and m2_conf >= CONFIG["confidence_threshold"]:
                committed = self.m2_post_processor.process(m2_pred, m2_conf)
                if committed:
                    prediction, confidence = committed
                    response.update({
                        "type": "inference_result",
                        "status": "success",
                        "prediction": prediction,
                        "confidence": float(round(confidence, 4)),
                    })

        # Step 5: M4 fallback (currently disabled when M2 is active)
        # (M4 sequence model was trained on synthetic data; M2 is more reliable)

        return response

    def close(self):
        """Release MediaPipe resources."""
        if getattr(self, "hand_landmarker", None) is not None:
            self.hand_landmarker.close()
            self.hand_landmarker = None
        if getattr(self, "pose_landmarker", None) is not None:
            self.pose_landmarker.close()
            self.pose_landmarker = None

    def run(self):
        """Standalone inference loop (for direct webcam use)."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("ERROR: Could not open webcam")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if not paused:
                result = self.process_frame(frame, mirror_input=True)
                if result.get("prediction"):
                    word = result["prediction"]
                    conf = result["confidence"]
                    transcript.append(word)
                    print(f"[*] Recognized: {word} ({conf:.2f})")

                # Draw landmarks on frame
                # (simplified for standalone mode)
                h, w = frame.shape[:2]
                cv2.putText(frame, f"FPS: {result.get('fps', 0):.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                if result.get("m2_prediction"):
                    cv2.putText(frame, f"M2: {result['m2_prediction']} ({result['m2_confidence']:.2f})",
                               (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            else:
                frame = cv2.flip(frame, 1)

            cv2.imshow("EchoSign M5 (q=quit, SPACE=pause, c=clear)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):
                paused = not paused
            elif key == ord('c'):
                transcript = []

        cap.release()
        self.close()
        cv2.destroyAllWindows()

        print("\n" + "="*60)
        print("Final Transcript:")
        print(" ".join(transcript) if transcript else "(empty)")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description="M5: Real-Time Inference")
    parser.add_argument("--model", default="models/sequence_model.pt",
                       help="Path to trained model")
    args = parser.parse_args()

    engine = LiveInferenceEngine(model_path=args.model)
    engine.run()


if __name__ == "__main__":
    main()
