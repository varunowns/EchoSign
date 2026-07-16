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
    "confidence_threshold": 0.15,  # lowered so M2 predictions flow to UI
    "cooldown_frames": 30,  # re-commit same sign every ~1 second at 30 FPS
    "fps": 30,
}


class PostProcessor:
    """
    Lightweight temporal smoothing for predictions.

    Uses a simple cooldown: once a prediction commits, subsequent identical
    predictions are suppressed for 'cooldown_frames'. After cooldown expires,
    the next frame prediction passes through immediately (no sliding window).
    """

    def __init__(self, cooldown_frames: int = 30):
        self.cooldown_frames = cooldown_frames
        self.last_committed = None
        self.silence_counter = 0  # frames since last commit

    def reset(self):
        """Clears all state. Call on WebSocket reconnect."""
        self.last_committed = None
        self.silence_counter = 0

    def process(self, prediction: str, confidence: float) -> Optional[Tuple[str, float]]:
        """
        Returns (prediction, confidence) after cooldown expires.

        - First prediction always passes through.
        - Same prediction is blocked until cooldown_frames have passed.
        - Different prediction passes immediately (hand sign change detected).
        """
        # Hand sign changed — commit immediately
        if self.last_committed is not None and prediction != self.last_committed:
            self.last_committed = prediction
            self.silence_counter = 0
            return prediction, confidence

        # Same as last committed — debounce via cooldown
        if prediction == self.last_committed:
            self.silence_counter += 1
            if self.silence_counter >= self.cooldown_frames:
                # Cooldown expired — re-commit to show user it's still active
                self.silence_counter = 0
                return prediction, confidence
            return None

        # First ever prediction
        self.last_committed = prediction
        self.silence_counter = 0
        return prediction, confidence


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

        # M2 gets its OWN post-processor (cooldown-based debounce)
        self.m2_post_processor = PostProcessor(
            cooldown_frames=CONFIG["cooldown_frames"]
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

    def predict_sequence(self) -> Tuple[Optional[str], float]:
        """Infer on buffered keypoint sequence using M4 LSTM model."""
        if not self.model or len(self.keypoint_buffer) < 10:
            return None, 0.0

        import numpy as np
        seq = np.array(list(self.keypoint_buffer))
        seq_len = len(seq)
        if seq_len < CONFIG["sequence_length"]:
            seq = np.pad(seq, ((0, CONFIG["sequence_length"] - seq_len), (0, 0)))
        else:
            seq = seq[:CONFIG["sequence_length"]]

        with torch.no_grad():
            x = torch.FloatTensor(seq).unsqueeze(0).to(self.device)
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)[0]
            conf, pred_idx = probs.max(dim=0)
            pred_char = chr(ord('A') + pred_idx.item())
            return pred_char, conf.item()

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

        # Step 4: Run M2 frame classifier — apply PostProcessor to gate commits
        if self.m2_classifier is not None and has_hands:
            m2_pred, m2_conf = self._predict_m2()
            response["prediction"] = m2_pred
            response["confidence"] = round(m2_conf, 4)
            if m2_pred and m2_conf >= CONFIG["confidence_threshold"]:
                # Gate through PostProcessor so the frontend does not get a
                # continuous firehose of "inference_result" every frame.
                committed = self.m2_post_processor.process(m2_pred, m2_conf)
                if committed is not None:
                    response["type"] = "inference_result"
                    response["status"] = "success"

        # Also run M4 sequence model for reference
        if self.model is not None and has_hands and len(self.keypoint_buffer) >= 30:
            m4_pred, m4_conf = self.predict_sequence()
            response["m4_prediction"] = m4_pred
            response["m4_confidence"] = round(m4_conf, 4)

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
