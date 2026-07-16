"""
M2 -- Static Gesture Classifier (Complete Implementation)
==========================================================
Single-frame ASL alphabet classification with full pipeline

Workflow:
1. Collect training data (26 letters × 20 samples = 520 frames)
2. Train Random Forest on extracted features
3. Evaluate accuracy
4. Use in real-time inference

Usage:
    python m2_static_classifier.py --train --data-dir data/raw
    python m2_static_classifier.py --test
"""

import os
import json
import pickle
import argparse
from pathlib import Path
from typing import Tuple, List, Dict
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import matplotlib.pyplot as plt


CONFIG = {
    "model_path": "models/asl_alphabet.pkl",
    "data_dir": "data/raw",
    "labels_file": "data/labels/asl_alphabet.json",
    "test_size": 0.2,
    "random_state": 42,
    "n_estimators": 100,
    "max_depth": 20,
}

ASL_ALPHABET = {chr(i): i - ord('A') for i in range(ord('A'), ord('Z') + 1)}
NUM_CLASSES = 26


class FrameFeatureExtractor:
    """Extract rich discriminative features from single keypoint frame.

    Feature categories (82 total):
      - Absolute positions (12): wrist, elbow, shoulder x/y
      - Hand centroids (4): left/right hand center x/y
      - Wrist-to-fingertip angles (20): 5 fingers x 2 hands x 2 (angle, length)
      - Inter-finger distances (20): finger-to-finger spreads for each hand
      - Finger curl ratios (10): distance from palm to fingertip vs palm to knuckle
      - Hand shape context (8): pairwise fingertip distances within each hand
      - Wrist-centroid vectors (4): vector from wrist to hand center for each hand
      - Confidence scores (2): mean hand detection confidence
      - Shoulder features (2): width, angle
    """

    @staticmethod
    def extract(keypoint: np.ndarray) -> np.ndarray:
        """Extract ~82 discriminative features from 300D keypoint vector."""
        pose = keypoint[:132].reshape(33, 4)
        left_hand = keypoint[132:216].reshape(21, 4)
        right_hand = keypoint[216:300].reshape(21, 4)

        features = []

        # ---- Absolute body landmark positions (12) ----
        left_wrist = pose[15, :2]
        right_wrist = pose[16, :2]
        left_elbow = pose[13, :2]
        right_elbow = pose[14, :2]
        left_shoulder = pose[11, :2]
        right_shoulder = pose[12, :2]
        features.extend(left_wrist); features.extend(right_wrist)
        features.extend(left_elbow); features.extend(right_elbow)
        features.extend(left_shoulder); features.extend(right_shoulder)

        # ---- Hand centroids (4) ----
        left_centroid = left_hand[:, :2].mean(axis=0)
        right_centroid = right_hand[:, :2].mean(axis=0)
        features.extend(left_centroid); features.extend(right_centroid)

        # ---- Wrist-to-centroid vectors (4) ----
        features.extend(right_centroid - right_wrist)
        features.extend(left_centroid - left_wrist)

        # ---- Finger features for each hand ----
        FINGER_TIPS = [4, 8, 12, 16, 20]  # thumb, index, middle, ring, pinky
        FINGER_DIPS = [3, 7, 11, 15, 19]   # second joint
        FINGER_MCPS = [2, 6, 10, 14, 18]   # knuckle (MCP)

        for hand in [left_hand, right_hand]:
            root = hand[0, :2]  # palm root (landmark 0)

            # Finger lengths (10): distance from wrist to each fingertip
            for tip_idx in FINGER_TIPS:
                tip = hand[tip_idx, :2]
                features.append(np.linalg.norm(tip - root))

            # Finger curl ratios (10): distal-to-tip distance / MCP-to-tip distance
            # Curled fingers have ratio near 1, extended fingers have ratio < 1
            for tip_idx, mcp_idx in zip(FINGER_TIPS, FINGER_MCPS):
                tip = hand[tip_idx, :2]
                mcp = hand[mcp_idx, :2]
                tip_to_root = np.linalg.norm(tip - root)
                mcp_to_root = np.linalg.norm(mcp - root)
                curl = tip_to_root / max(mcp_to_root, 1e-6)
                features.append(curl)

            # Inter-finger spreads (4): distance between adjacent fingertips
            for i in range(len(FINGER_TIPS) - 1):
                tip1 = hand[FINGER_TIPS[i], :2]
                tip2 = hand[FINGER_TIPS[i+1], :2]
                features.append(np.linalg.norm(tip1 - tip2))

            # Finger-to-finger angles (6): angle between each finger pair
            # This is key for distinguishing B (parallel) from C (curved)
            for i in range(len(FINGER_TIPS)):
                for j in range(i+1, len(FINGER_TIPS)):
                    v1 = hand[FINGER_TIPS[i], :2] - root
                    v2 = hand[FINGER_TIPS[j], :2] - root
                    dot = np.dot(v1, v2)
                    norms = np.linalg.norm(v1) * np.linalg.norm(v2)
                    cos_angle = dot / max(norms, 1e-6)
                    features.append(cos_angle)  # -1 to 1

            # Distance from each fingertip to the centroid (shape context, 5)
            for tip_idx in FINGER_TIPS:
                features.append(np.linalg.norm(hand[tip_idx, :2] - right_centroid))

            # Hand opening ratio: spread of furthest fingers vs palm size
            pinky_tip = hand[20, :2]
            thumb_tip = hand[4, :2]
            max_spread = np.linalg.norm(pinky_tip - thumb_tip)
            features.append(max_spread)

            # Wrist-to-fingertip vector direction (2 per hand): mean direction
            vectors = [hand[ti, :2] - root for ti in FINGER_TIPS]
            mean_vec = np.mean(vectors, axis=0)
            features.extend(mean_vec / max(np.linalg.norm(mean_vec), 1e-6))

        # ---- Hand detection confidence (2) ----
        features.append(left_hand[:, 3].mean())
        features.append(right_hand[:, 3].mean())

        # ---- Shoulder features (2) ----
        shoulder_width = np.linalg.norm(right_shoulder - left_shoulder)
        features.append(shoulder_width)
        shoulder_vector = right_shoulder - left_shoulder
        features.append(np.arctan2(shoulder_vector[1], shoulder_vector[0]))

        return np.array(features)

    @staticmethod
    def extract_batch(keypoints: np.ndarray) -> np.ndarray:
        """Extract features from batch of frames."""
        features_list = [FrameFeatureExtractor.extract(kp) for kp in keypoints]
        return np.array(features_list)

    @staticmethod
    def extract_batch(keypoints: np.ndarray) -> np.ndarray:
        """Extract features from batch of frames."""
        features_list = [FrameFeatureExtractor.extract(kp) for kp in keypoints]
        return np.array(features_list)


class StaticGestureClassifier:
    """Random Forest classifier for ASL alphabet."""

    def __init__(self, n_estimators: int = 100, max_depth: int = 20):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=CONFIG["random_state"],
            n_jobs=-1,
        )
        self.feature_extractor = FrameFeatureExtractor()
        self.classes = list(ASL_ALPHABET.keys())
        self.is_trained = False

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        """Train classifier."""
        self.model.fit(X_train, y_train)
        self.is_trained = True

    def predict(self, keypoint: np.ndarray) -> Tuple[str, float]:
        """Predict single frame."""
        if not self.is_trained:
            raise RuntimeError("Model not trained yet")

        features = self.feature_extractor.extract(keypoint)
        features = features.reshape(1, -1)

        pred_idx = self.model.predict(features)[0]
        confidence = self.model.predict_proba(features)[0].max()

        letter = self.classes[pred_idx]
        return letter, confidence

    def predict_batch(self, keypoints: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict batch of frames."""
        features = self.feature_extractor.extract_batch(keypoints)
        preds = self.model.predict(features)
        confs = self.model.predict_proba(features).max(axis=1)
        return preds, confs

    def save(self, path: str):
        """Save model to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'classes': self.classes,
                'is_trained': self.is_trained,
            }, f)
        print(f"[OK] Model saved to {path}")

    @classmethod
    def load(cls, path: str):
        """Load model from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        obj = cls()
        obj.model = data['model']
        obj.classes = data['classes']
        obj.is_trained = data['is_trained']
        print(f"[OK] Model loaded from {path}")
        return obj


def load_training_data(data_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load keypoint sequences from raw data files."""
    X_list, y_list = [], []

    data_path = Path(data_dir)
    for npy_file in sorted(data_path.glob("*.npy")):
        # Parse filename: LABEL_SESSION_NUM.npy
        label = npy_file.stem.split("_")[0]
        if label in ASL_ALPHABET:
            X = np.load(npy_file)
            y = np.full(len(X), ASL_ALPHABET[label])
            X_list.append(X)
            y_list.append(y)

    if not X_list:
        raise FileNotFoundError(f"No training data in {data_dir}")

    X = np.vstack(X_list)
    y = np.hstack(y_list)

    return X, y


def train_classifier():
    """Train static gesture classifier."""
    print("="*60)
    print("M2: Static Gesture Classifier - Training")
    print("="*60)

    # Load data
    print(f"\nLoading training data from {CONFIG['data_dir']}...")
    try:
        X, y = load_training_data(CONFIG["data_dir"])
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Run data_collector.py to record training data first")
        return None

    print(f"Total samples: {len(X)}")

    # Extract features
    print("Extracting frame features...")
    feature_extractor = FrameFeatureExtractor()
    X_features = feature_extractor.extract_batch(X)
    print(f"Feature shape: {X_features.shape}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_features, y,
        test_size=CONFIG["test_size"],
        random_state=CONFIG["random_state"],
        stratify=y
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Train
    print("\nTraining Random Forest...")
    classifier = StaticGestureClassifier(
        n_estimators=CONFIG["n_estimators"],
        max_depth=CONFIG["max_depth"],
    )
    classifier.train(X_train, y_train)

    # Evaluate
    print("\nEvaluating...")
    y_pred = classifier.model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Test accuracy: {accuracy:.4f}")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=list(ASL_ALPHABET.keys())))

    # Save
    classifier.save(CONFIG["model_path"])
    return classifier


def main():
    parser = argparse.ArgumentParser(description="M2: Static Gesture Classifier")
    parser.add_argument("--train", action="store_true", help="Train classifier")
    parser.add_argument("--data-dir", default=CONFIG["data_dir"])
    args = parser.parse_args()

    if args.train:
        train_classifier()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
