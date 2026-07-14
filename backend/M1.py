"""
M1 -- Webcam capture + MediaPipe landmark visualization
--------------------------------------------------------
Run this locally (on a machine with a webcam + display).

NOTE ON API VERSION: this uses the current MediaPipe Tasks API
(HandLandmarker + PoseLandmarker), not the old `mp.solutions.holistic`
API. That legacy "Solutions" API was deprecated in March 2023 and no
longer works in current MediaPipe pip releases (`mp.solutions` doesn't
exist anymore). The Tasks API's own HolisticLandmarker is still listed
as "coming soon" upstream and its model file location has moved around
across issues, so this script instead combines two Tasks API components
that ARE stable and documented: HandLandmarker (both hands) and
PoseLandmarker (upper body). Together they cover everything v1 needs;
face landmarks are out of scope for now per the PRD.

Install:
    pip install opencv-python mediapipe

Download the two model files (one-time, ~30MB total):
    wget -O hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
    wget -O pose_landmarker.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task

    (On Windows without wget, just paste those two URLs into a browser
    and save the files next to this script.)

Run:
    python m1_landmark_viewer.py

Controls:
    q  -  quit
    s  -  print current normalized keypoint vector shape to console
          (sanity check for what M2/M3 will consume)
"""

import cv2
import mediapipe as mp
import numpy as np
import time

from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker, HandLandmarkerOptions,
    PoseLandmarker, PoseLandmarkerOptions,
    RunningMode,
)

HAND_MODEL_PATH = "hand_landmarker.task"
POSE_MODEL_PATH = "pose_landmarker.task"

# Standard 21-point hand connections (thumb, index, middle, ring, pinky, palm)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (0, 17),                                 # palm base
]

# Upper-body subset of the 33 pose landmarks (indices per MediaPipe pose spec)
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # shoulders + arms
    (11, 23), (12, 24), (23, 24),                       # torso
]


def extract_keypoints(hand_result, pose_result):
    """
    Flatten pose + both-hand landmarks into a single fixed-size vector.
    Missing landmarks (hand out of frame, etc.) are zero-filled so the
    output shape is always consistent -- required for the sequence
    model buffer later (M3/M4).
    """
    # Pose: 33 landmarks x (x, y, z, visibility)
    if pose_result.pose_landmarks:
        lm_list = pose_result.pose_landmarks[0]
        pose = np.array([[lm.x, lm.y, lm.z, lm.visibility] for lm in lm_list]).flatten()
    else:
        pose = np.zeros(33 * 4)

    # Hands: MediaPipe doesn't guarantee left/right order, so we sort by
    # handedness label. Each hand: 21 landmarks x (x, y, z).
    left_hand = np.zeros(21 * 3)
    right_hand = np.zeros(21 * 3)
    if hand_result.hand_landmarks:
        for lm_list, handedness in zip(hand_result.hand_landmarks, hand_result.handedness):
            coords = np.array([[lm.x, lm.y, lm.z] for lm in lm_list]).flatten()
            label = handedness[0].category_name  # "Left" or "Right"
            if label == "Left":
                left_hand = coords
            else:
                right_hand = coords

    return np.concatenate([pose, left_hand, right_hand])


def normalize_keypoints(keypoints):
    """
    Center on shoulder midpoint, scale by shoulder width, so the model
    is invariant to how close/far the signer is from the camera.
    Pose block is the first 132 values (33 landmarks x 4). Shoulders
    are pose landmarks 11 (left) and 12 (right).
    """
    pose = keypoints[:132].reshape(33, 4)
    left_shoulder = pose[11, :2]
    right_shoulder = pose[12, :2]

    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    shoulder_width = np.linalg.norm(right_shoulder - left_shoulder)
    if shoulder_width < 1e-6:
        shoulder_width = 1.0  # avoid divide-by-zero when pose isn't detected

    normalized = keypoints.copy()
    for i in range(33):
        normalized[i * 4] = (keypoints[i * 4] - shoulder_mid[0]) / shoulder_width
        normalized[i * 4 + 1] = (keypoints[i * 4 + 1] - shoulder_mid[1]) / shoulder_width

    return normalized


def draw_landmarks(frame, landmarks_norm, connections, color):
    h, w = frame.shape[:2]
    points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks_norm]
    for a, b in connections:
        if a < len(points) and b < len(points):
            cv2.line(frame, points[a], points[b], color, 2)
    for p in points:
        cv2.circle(frame, p, 3, color, -1)


def main():
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

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: could not open webcam. Check camera index/permissions.")
        return

    prev_time = 0
    start_time = time.time()

    with HandLandmarker.create_from_options(hand_options) as hand_landmarker, \
         PoseLandmarker.create_from_options(pose_options) as pose_landmarker:

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame.")
                break

            frame = cv2.flip(frame, 1)  # mirror for natural interaction
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            timestamp_ms = int((time.time() - start_time) * 1000)

            hand_result = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
            pose_result = pose_landmarker.detect_for_video(mp_image, timestamp_ms)

            # Draw pose (upper body subset)
            if pose_result.pose_landmarks:
                draw_landmarks(frame, pose_result.pose_landmarks[0], POSE_CONNECTIONS, (0, 255, 0))

            # Draw hands
            if hand_result.hand_landmarks:
                for lm_list in hand_result.hand_landmarks:
                    draw_landmarks(frame, lm_list, HAND_CONNECTIONS, (255, 255, 0))

            # FPS counter -- latency sanity check
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if prev_time else 0
            prev_time = curr_time
            cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            num_hands = len(hand_result.hand_landmarks) if hand_result.hand_landmarks else 0
            has_pose = bool(pose_result.pose_landmarks)
            status = f"Hands detected: {num_hands}  Pose: {'Y' if has_pose else 'N'}"
            cv2.putText(frame, status, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            cv2.imshow("M1 - Landmark Viewer (q to quit, s to inspect keypoints)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                kp = extract_keypoints(hand_result, pose_result)
                norm_kp = normalize_keypoints(kp)
                print(f"Raw keypoint vector shape: {kp.shape}")
                print(f"Normalized keypoint vector shape: {norm_kp.shape}")
                print(f"Sample values (first 8): {norm_kp[:8]}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()