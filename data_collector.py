"""
Data Collector -- Record and label keypoint sequences
======================================================
EchoSign utility for collecting training data

This script:
1. Captures live video from M1 (keypoint extraction)
2. Records keypoint sequences for a labeled gesture
3. Saves as .npy files with metadata
4. Prepares data for M2/M4 training

Data format:
- Output: .npy file with shape (num_frames, 300)
- Naming: {LABEL}_{SESSION}_{SAMPLE}.npy (e.g., A_session1_001.npy)
- Metadata: JSON file with label, date, duration, quality info

Usage:
    # Record 20 samples of ASL letter "A"
    python data_collector.py --label A --samples 20

    # Record 10 samples with custom duration (2 seconds each)
    python data_collector.py --label hello --samples 10 --duration 2

    # Review collected data
    python data_collector.py --review

    # Process raw data into train/test splits
    python data_collector.py --process-data
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker, HandLandmarkerOptions,
    PoseLandmarker, PoseLandmarkerOptions,
    RunningMode,
)

# Configuration
CONFIG = {
    "hand_model": "hand_landmarker.task",
    "pose_model": "pose_landmarker.task",
    "data_dir": "data/raw",
    "processed_dir": "data/processed",
    "labels_dir": "data/labels",
    "default_duration": 1.5,  # seconds
    "fps": 30,
}

# Hand and pose connection definitions (same as M1)
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


def extract_keypoints(hand_result, pose_result) -> np.ndarray:
    """Extract and flatten all landmarks (same as M1)."""
    pose_vec = np.zeros(33 * 4)
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        pose_vec = np.array(
            [[lm.x, lm.y, lm.z, lm.visibility] for lm in pose_landmarks]
        ).flatten()

    left_hand = np.zeros(21 * 4)
    right_hand = np.zeros(21 * 4)

    if hand_result.hand_landmarks:
        for lm_list, handedness in zip(
            hand_result.hand_landmarks, hand_result.handedness
        ):
            hand_confidence = handedness[0].score
            coords = np.array(
                [[lm.x, lm.y, lm.z, hand_confidence] for lm in lm_list]
            ).flatten()

            label = handedness[0].category_name
            if label == "Left":
                left_hand = coords
            else:
                right_hand = coords

    return np.concatenate([pose_vec, left_hand, right_hand])


def normalize_keypoints(keypoints: np.ndarray) -> np.ndarray:
    """Normalize keypoints (same as M1)."""
    pose = keypoints[:132].reshape(33, 4)
    left_hand = keypoints[132:216].reshape(21, 4)
    right_hand = keypoints[216:300].reshape(21, 4)

    left_shoulder = pose[11, :2]
    right_shoulder = pose[12, :2]

    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    shoulder_width = np.linalg.norm(right_shoulder - left_shoulder)

    if shoulder_width < 1e-6:
        shoulder_width = 1.0

    normalized = keypoints.copy()

    for i in range(33):
        normalized[i * 4] = (keypoints[i * 4] - shoulder_mid[0]) / shoulder_width
        normalized[i * 4 + 1] = (keypoints[i * 4 + 1] - shoulder_mid[1]) / shoulder_width
        normalized[i * 4 + 2] = keypoints[i * 4 + 2] / shoulder_width

    for i in range(21):
        idx = 132 + i * 4
        normalized[idx] = (keypoints[idx] - shoulder_mid[0]) / shoulder_width
        normalized[idx + 1] = (keypoints[idx + 1] - shoulder_mid[1]) / shoulder_width
        normalized[idx + 2] = keypoints[idx + 2] / shoulder_width

    for i in range(21):
        idx = 216 + i * 4
        normalized[idx] = (keypoints[idx] - shoulder_mid[0]) / shoulder_width
        normalized[idx + 1] = (keypoints[idx + 1] - shoulder_mid[1]) / shoulder_width
        normalized[idx + 2] = keypoints[idx + 2] / shoulder_width

    return normalized


def draw_landmarks_on_frame(frame, hand_result, pose_result):
    """Draw skeleton overlay (same as M1)."""
    h, w = frame.shape[:2]

    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        for start_idx, end_idx in POSE_CONNECTIONS:
            start = pose_landmarks[start_idx]
            end = pose_landmarks[end_idx]
            start_pos = (int(start.x * w), int(start.y * h))
            end_pos = (int(end.x * w), int(end.y * h))
            cv2.line(frame, start_pos, end_pos, color=(0, 255, 0), thickness=2)

        for landmark in pose_landmarks:
            pos = (int(landmark.x * w), int(landmark.y * h))
            cv2.circle(frame, pos, radius=4, color=(0, 255, 0), thickness=-1)

    if hand_result.hand_landmarks:
        for hand_idx, (hand_landmarks, handedness) in enumerate(
            zip(hand_result.hand_landmarks, hand_result.handedness)
        ):
            color = (255, 255, 0) if handedness[0].category_name == "Right" else (255, 0, 255)

            for start_idx, end_idx in HAND_CONNECTIONS:
                start = hand_landmarks[start_idx]
                end = hand_landmarks[end_idx]
                start_pos = (int(start.x * w), int(start.y * h))
                end_pos = (int(end.x * w), int(end.y * h))
                cv2.line(frame, start_pos, end_pos, color=color, thickness=1)

            for landmark in hand_landmarks:
                pos = (int(landmark.x * w), int(landmark.y * h))
                cv2.circle(frame, pos, radius=3, color=color, thickness=-1)


def record_gesture(label: str, duration: float = CONFIG["default_duration"]) -> Tuple[np.ndarray, dict]:
    """
    Record a single gesture sample and return keypoint sequence + metadata.

    Args:
        label: gesture label (e.g., "A", "hello")
        duration: recording duration in seconds

    Returns:
        (keypoints, metadata): keypoints shape (num_frames, 300), metadata dict
    """
    hand_options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=CONFIG["hand_model"]),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=CONFIG["pose_model"]),
        running_mode=RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam")
        return None, None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    keypoints_list = []
    frame_count = 0
    target_frames = int(duration * CONFIG["fps"])
    start_time = None
    timestamp_start = 0

    print(f"\n{'=' * 60}")
    print(f"Recording gesture: {label}")
    print(f"Duration: {duration}s (~{target_frames} frames)")
    print(f"Press 'SPACE' to START, 'q' to CANCEL")
    print(f"{'=' * 60}\n")

    recording = False

    with HandLandmarker.create_from_options(hand_options) as hand_landmarker, \
         PoseLandmarker.create_from_options(pose_options) as pose_landmarker:

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Get timestamp (ms since start)
            if start_time is None:
                start_time = datetime.now()
                timestamp_start = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)

            timestamp_ms = int((cv2.getTickCount() / cv2.getTickFrequency() - timestamp_start / 1000) * 1000)

            hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
            pose_result = pose_landmarker.detect_for_video(mp_image, timestamp_ms)

            # Draw landmarks
            draw_landmarks_on_frame(frame, hand_result, pose_result)

            # Record keypoints if recording
            if recording:
                kp = extract_keypoints(hand_result, pose_result)
                kp_norm = normalize_keypoints(kp)
                keypoints_list.append(kp_norm)
                frame_count += 1

                # Progress bar
                progress = frame_count / target_frames
                bar_len = 40
                filled = int(bar_len * progress)
                bar = "█" * filled + "░" * (bar_len - filled)
                cv2.putText(frame, f"Recording: [{bar}] {frame_count}/{target_frames}",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                if frame_count >= target_frames:
                    print(f"✓ Recording complete ({frame_count} frames)")
                    break
            else:
                cv2.putText(frame, "WAITING - Press SPACE to start recording",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

            cv2.imshow("Data Collector - Press SPACE to record, q to cancel", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("❌ Cancelled")
                cap.release()
                cv2.destroyAllWindows()
                return None, None
            elif key == ord(' '):
                if not recording:
                    recording = True
                    print(f"▶ Recording started...")

    cap.release()
    cv2.destroyAllWindows()

    # Prepare metadata
    metadata = {
        "label": label,
        "timestamp": start_time.isoformat(),
        "num_frames": frame_count,
        "duration_sec": duration,
        "fps": CONFIG["fps"],
    }

    keypoints_array = np.array(keypoints_list)  # shape: (num_frames, 300)
    return keypoints_array, metadata


def save_sample(label: str, keypoints: np.ndarray, metadata: dict, session: str = "session1"):
    """Save a single sample to disk."""
    Path(CONFIG["data_dir"]).mkdir(parents=True, exist_ok=True)

    # Find next sample number
    existing = list(Path(CONFIG["data_dir"]).glob(f"{label}_{session}_*.npy"))
    sample_num = len(existing) + 1
    sample_name = f"{label}_{session}_{sample_num:03d}"

    # Save keypoints
    keypoint_path = Path(CONFIG["data_dir"]) / f"{sample_name}.npy"
    np.save(keypoint_path, keypoints)

    # Save metadata
    metadata_path = Path(CONFIG["data_dir"]) / f"{sample_name}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Saved: {keypoint_path} ({keypoints.shape[0]} frames)")
    return keypoint_path


def collect_samples(label: str, num_samples: int, duration: float = CONFIG["default_duration"]):
    """Collect multiple samples for a label."""
    print(f"\n{'=' * 60}")
    print(f"EchoSign Data Collector - {label.upper()}")
    print(f"Target: {num_samples} samples, {duration}s each")
    print(f"{'=' * 60}")

    session = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(num_samples):
        print(f"\n[Sample {i+1}/{num_samples}]")
        keypoints, metadata = record_gesture(label, duration)

        if keypoints is not None:
            save_sample(label, keypoints, metadata, session)
        else:
            print(f"⏭ Skipped sample {i+1}")

    print(f"\n✓ Collection complete for {label}")


def review_data():
    """Review collected data."""
    data_dir = Path(CONFIG["data_dir"])
    files = list(data_dir.glob("*.npy"))

    if not files:
        print("No data found in", data_dir)
        return

    print(f"\n{'=' * 60}")
    print(f"EchoSign Data Review")
    print(f"{'=' * 60}\n")

    # Organize by label
    by_label = {}
    for npy_file in files:
        label = npy_file.stem.split("_")[0]
        if label not in by_label:
            by_label[label] = []
        by_label[label].append(npy_file)

    total_samples = 0
    total_frames = 0

    for label in sorted(by_label.keys()):
        samples = by_label[label]
        frame_counts = []

        for sample_file in samples:
            data = np.load(sample_file)
            frame_counts.append(data.shape[0])
            total_frames += data.shape[0]

        avg_frames = int(np.mean(frame_counts))
        total_samples += len(samples)

        print(f"  {label:10s}: {len(samples):3d} samples, {avg_frames:3d} frames avg")

    print(f"\n  Total: {total_samples} samples, {total_frames} frames")


def main():
    parser = argparse.ArgumentParser(description="EchoSign Data Collector")
    parser.add_argument("--label", type=str, help="Gesture label to record (e.g., A, B, hello)")
    parser.add_argument("--samples", type=int, default=1, help="Number of samples to record")
    parser.add_argument("--duration", type=float, default=CONFIG["default_duration"],
                       help="Recording duration per sample (seconds)")
    parser.add_argument("--review", action="store_true", help="Review collected data")
    parser.add_argument("--process-data", action="store_true", help="Process data into train/test splits")

    args = parser.parse_args()

    if args.review:
        review_data()
    elif args.process_data:
        print("Data processing not yet implemented")
        print("TODO: Split raw data into train/test/val sets by session")
    elif args.label:
        collect_samples(args.label, args.samples, args.duration)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
