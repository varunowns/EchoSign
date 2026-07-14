"""
M1 -- Webcam capture + MediaPipe landmark visualization
========================================================
EchoSign: Real-Time Sign Language Translator
Milestone 1: Real-time keypoint extraction and visualization

Uses MediaPipe Tasks API (HandLandmarker + PoseLandmarker):
- 21 landmarks per hand × 2 hands (x, y, z, confidence)
- 33 pose landmarks (x, y, z, visibility)
- Normalized relative to shoulder midpoint for camera-invariant features

Install:
    pip install opencv-python mediapipe numpy

Download model files (one-time, ~37MB total):
    wget -O hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
    wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task

Run:
    python M1_improved.py

Controls:
    q  -  quit
    s  -  print normalized keypoint vector info to console
    SPACE  -  pause/resume video
"""

import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque

from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker, HandLandmarkerOptions,
    PoseLandmarker, PoseLandmarkerOptions,
    RunningMode,
)

HAND_MODEL_PATH = "hand_landmarker.task"
POSE_MODEL_PATH = "pose_landmarker.task"

# Standard 21-point hand skeleton connections (MediaPipe format)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),                  # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),                  # index
    (5, 9), (9, 10), (10, 11), (11, 12),             # middle
    (9, 13), (13, 14), (14, 15), (15, 16),           # ring
    (13, 17), (17, 18), (18, 19), (19, 20),          # pinky
    (0, 17),                                          # palm base
]

# Upper-body pose skeleton (33 pose landmarks -> 8 key connections for v1)
# MediaPipe pose indices: 11=left shoulder, 12=right shoulder, 13=left elbow,
# 14=right elbow, 15=left wrist, 16=right wrist, 23=left hip, 24=right hip
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # shoulders + arms
    (11, 23), (12, 24), (23, 24),                       # torso
]


def extract_keypoints(hand_result, pose_result):
    """
    Extract and flatten all landmarks into a single fixed-size vector.

    Output structure:
    - Pose: 33 landmarks × (x, y, z, visibility) = 132 values
    - Left hand: 21 landmarks × (x, y, z, confidence) = 84 values
    - Right hand: 21 landmarks × (x, y, z, confidence) = 84 values
    Total: 300 values

    Missing landmarks are zero-filled for consistent shape.
    This ensures M2/M3 models always receive fixed-size input.
    """
    # Extract pose landmarks (always 33, may be unfilled)
    pose_vec = np.zeros(33 * 4)  # 132 values
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        pose_vec = np.array(
            [[lm.x, lm.y, lm.z, lm.visibility] for lm in pose_landmarks]
        ).flatten()

    # Extract hand landmarks - MediaPipe doesn't guarantee left/right order,
    # so we match by handedness label. Each hand gets 21 landmarks.
    left_hand = np.zeros(21 * 4)   # 84 values (x, y, z, confidence)
    right_hand = np.zeros(21 * 4)  # 84 values

    if hand_result.hand_landmarks:
        for lm_list, handedness in zip(
            hand_result.hand_landmarks, hand_result.handedness
        ):
            # Each landmark has x, y, z; handedness provides confidence
            hand_confidence = handedness[0].score  # 0.0-1.0
            coords = np.array([[lm.x, lm.y, lm.z, hand_confidence] for lm in lm_list]).flatten()

            label = handedness[0].category_name  # "Left" or "Right"
            if label == "Left":
                left_hand = coords
            else:
                right_hand = coords

    return np.concatenate([pose_vec, left_hand, right_hand])


def normalize_keypoints(keypoints):
    """
    Normalize keypoints to be invariant to camera distance and body size.

    Method:
    1. Extract shoulder positions (pose landmarks 11 and 12)
    2. Center all landmarks on shoulder midpoint
    3. Scale all landmarks by shoulder width
    4. Apply to pose, left hand, AND right hand for consistency

    This makes the model robust to different signer positions/distances.
    """
    pose = keypoints[:132].reshape(33, 4)
    left_hand = keypoints[132:216].reshape(21, 4)
    right_hand = keypoints[216:300].reshape(21, 4)

    # Get shoulder landmarks (MediaPipe indices 11 and 12)
    left_shoulder = pose[11, :2]
    right_shoulder = pose[12, :2]

    # Compute shoulder center and width for normalization
    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    shoulder_width = np.linalg.norm(right_shoulder - left_shoulder)

    # Avoid division by zero if shoulder not detected
    if shoulder_width < 1e-6:
        shoulder_width = 1.0

    normalized = keypoints.copy()

    # Normalize pose landmarks (all 33)
    for i in range(33):
        normalized[i * 4] = (keypoints[i * 4] - shoulder_mid[0]) / shoulder_width
        normalized[i * 4 + 1] = (keypoints[i * 4 + 1] - shoulder_mid[1]) / shoulder_width
        # Also normalize z (depth) for full invariance
        normalized[i * 4 + 2] = keypoints[i * 4 + 2] / shoulder_width

    # Normalize left hand landmarks (21, with confidence in 4th channel)
    for i in range(21):
        idx = 132 + i * 4
        normalized[idx] = (keypoints[idx] - shoulder_mid[0]) / shoulder_width
        normalized[idx + 1] = (keypoints[idx + 1] - shoulder_mid[1]) / shoulder_width
        normalized[idx + 2] = keypoints[idx + 2] / shoulder_width

    # Normalize right hand landmarks (21, with confidence in 4th channel)
    for i in range(21):
        idx = 216 + i * 4
        normalized[idx] = (keypoints[idx] - shoulder_mid[0]) / shoulder_width
        normalized[idx + 1] = (keypoints[idx + 1] - shoulder_mid[1]) / shoulder_width
        normalized[idx + 2] = keypoints[idx + 2] / shoulder_width

    return normalized


def draw_landmarks_on_frame(frame, hand_result, pose_result):
    """
    Draw skeleton overlays on the video frame.

    Draws:
    - Pose skeleton in green (upper body)
    - Left hand skeleton in cyan
    - Right hand skeleton in yellow
    """
    h, w = frame.shape[:2]

    # Draw pose landmarks and connections
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]

        # Draw connections first (so they appear behind points)
        for start_idx, end_idx in POSE_CONNECTIONS:
            start = pose_landmarks[start_idx]
            end = pose_landmarks[end_idx]

            start_pos = (int(start.x * w), int(start.y * h))
            end_pos = (int(end.x * w), int(end.y * h))

            cv2.line(frame, start_pos, end_pos, color=(0, 255, 0), thickness=2)

        # Draw pose landmark circles
        for landmark in pose_landmarks:
            pos = (int(landmark.x * w), int(landmark.y * h))
            cv2.circle(frame, pos, radius=4, color=(0, 255, 0), thickness=-1)

    # Draw hand landmarks and connections
    if hand_result.hand_landmarks:
        for hand_idx, (hand_landmarks, handedness) in enumerate(
            zip(hand_result.hand_landmarks, hand_result.handedness)
        ):
            # Color by hand: left=cyan, right=yellow
            color = (255, 255, 0) if handedness[0].category_name == "Right" else (255, 0, 255)

            # Draw connections
            for start_idx, end_idx in HAND_CONNECTIONS:
                start = hand_landmarks[start_idx]
                end = hand_landmarks[end_idx]

                start_pos = (int(start.x * w), int(start.y * h))
                end_pos = (int(end.x * w), int(end.y * h))

                cv2.line(frame, start_pos, end_pos, color=color, thickness=1)

            # Draw landmark circles
            for landmark in hand_landmarks:
                pos = (int(landmark.x * w), int(landmark.y * h))
                cv2.circle(frame, pos, radius=3, color=color, thickness=-1)


def draw_hud(frame, fps, num_hands, has_pose, normalized_kp=None):
    """
    Draw heads-up display with FPS, detection status, and optional keypoint info.
    """
    cv2.putText(
        frame, f"FPS: {fps:.1f}", (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
    )

    status = f"Hands: {num_hands}  Pose: {'✓' if has_pose else '✗'}"
    cv2.putText(
        frame, status, (10, 65),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
    )

    if normalized_kp is not None:
        kp_info = f"Keypoints: {normalized_kp.shape[0]} dims"
        cv2.putText(
            frame, kp_info, (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1
        )


def main():
    # Initialize MediaPipe models with appropriate options
    hand_options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=HAND_MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    pose_options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=POSE_MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam. Check camera index/permissions.")
        return

    # Attempt to set camera to 30 FPS (may not work on all cameras)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_time = 0
    start_time = time.time()
    fps_history = deque(maxlen=10)  # Track last 10 frames for smoothed FPS
    paused = False

    print("=" * 60)
    print("EchoSign M1 - Real-time Landmark Extraction & Visualization")
    print("=" * 60)
    print("Controls:")
    print("  q     - Quit")
    print("  s     - Print keypoint info")
    print("  SPACE - Pause/Resume")
    print("=" * 60)

    with HandLandmarker.create_from_options(hand_options) as hand_landmarker, \
         PoseLandmarker.create_from_options(pose_options) as pose_landmarker:

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame. Exiting.")
                break

            # Mirror frame for natural interaction
            frame = cv2.flip(frame, 1)

            # Only process frames when not paused
            if not paused:
                # Convert BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                # Calculate timestamp for video mode
                timestamp_ms = int((time.time() - start_time) * 1000)

                # Run landmark detection
                hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
                pose_result = pose_landmarker.detect_for_video(mp_image, timestamp_ms)

                # Draw landmarks on frame
                draw_landmarks_on_frame(frame, hand_result, pose_result)

                # Extract and normalize keypoints (for M2/M3 pipeline)
                raw_kp = extract_keypoints(hand_result, pose_result)
                norm_kp = normalize_keypoints(raw_kp)

                # Compute smoothed FPS
                curr_time = time.time()
                if prev_time > 0:
                    frame_time = curr_time - prev_time
                    fps = 1.0 / frame_time if frame_time > 0 else 0
                    fps_history.append(fps)
                prev_time = curr_time

                # Count detections for display
                num_hands = len(hand_result.hand_landmarks) if hand_result.hand_landmarks else 0
                has_pose = bool(pose_result.pose_landmarks)

            else:
                # Paused - show placeholder landmarks
                hand_result = None
                pose_result = None
                norm_kp = None
                num_hands = 0
                has_pose = False
                fps_history.append(0)

            # Draw HUD
            avg_fps = np.mean(fps_history) if fps_history else 0
            draw_hud(frame, avg_fps, num_hands, has_pose, norm_kp if not paused else None)

            # Add pause indicator
            if paused:
                cv2.putText(
                    frame, "PAUSED (SPACE to resume)", (10, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                )

            cv2.imshow("EchoSign M1 - Landmark Viewer (q=quit, s=inspect, SPACE=pause)", frame)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nExiting...")
                break
            elif key == ord('s'):
                # Print keypoint information
                if not paused and norm_kp is not None:
                    print("\n" + "=" * 60)
                    print("Keypoint Vector Information:")
                    print("=" * 60)
                    print(f"Raw keypoint shape: {raw_kp.shape}")
                    print(f"Normalized keypoint shape: {norm_kp.shape}")
                    print(f"\nStructure breakdown:")
                    print(f"  Pose (33 lm × 4 ch): indices 0-131")
                    print(f"  Left hand (21 lm × 4 ch): indices 132-215")
                    print(f"  Right hand (21 lm × 4 ch): indices 216-299")
                    print(f"\nSample normalized values (first 8): {norm_kp[:8]}")
                    print(f"Shoulder-normalized (invariant to distance/size)")
                    print("=" * 60 + "\n")
            elif key == ord(' '):
                paused = not paused
                status = "PAUSED" if paused else "RESUMED"
                print(f"\n>>> Video {status}")

    cap.release()
    cv2.destroyAllWindows()
    print("Cleanup complete.")


if __name__ == "__main__":
    main()
