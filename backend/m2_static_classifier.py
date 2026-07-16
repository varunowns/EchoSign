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
    """Extract features from single keypoint frame."""

    @staticmethod
    def extract(keypoint: np.ndarray) -> np.ndarray:
        """Extract 40+ dimensional features from 300D keypoint vector."""
        pose = keypoint[:132].reshape(33, 4)
        left_hand = keypoint[132:216].reshape(21, 4)
        right_hand = keypoint[216:300].reshape(21, 4)

        features = []

        # Hand centroids
        left_centroid = left_hand[:, :2].mean(axis=0)
        right_centroid = right_hand[:, :2].mean(axis=0)
        features.extend(left_centroid)
        features.extend(right_centroid)

        # Hand distance
        hand_distance = np.linalg.norm(right_centroid - left_centroid)
        features.append(hand_distance)

        # Wrist positions
        left_wrist = pose[15, :2]
        right_wrist = pose[16, :2]
        features.extend(left_wrist)
        features.extend(right_wrist)

        # Confidence
        left_conf = left_hand[:, 3].mean()
        right_conf = right_hand[:, 3].mean()
        features.extend([left_conf, right_conf])

        # Finger spreads
        left_root = left_hand[0, :2]
        left_fingertips = [left_hand[i, :2] for i in [4, 8, 12, 16, 20]]
        left_spreads = [np.linalg.norm(ft - left_root) for ft in left_fingertips]
        features.extend(left_spreads)

        right_root = right_hand[0, :2]
        right_fingertips = [right_hand[i, :2] for i in [4, 8, 12, 16, 20]]
        right_spreads = [np.linalg.norm(ft - right_root) for ft in right_fingertips]
        features.extend(right_spreads)

        # Shoulder angle
        left_shoulder = pose[11, :2]
        right_shoulder = pose[12, :2]
        shoulder_vector = right_shoulder - left_shoulder
        shoulder_angle = np.arctan2(shoulder_vector[1], shoulder_vector[0])
        features.append(shoulder_angle)

        return np.array(features)

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
