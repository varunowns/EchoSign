"""
M3 -- Dynamic Gesture Data Pipeline
====================================
Processes raw keypoint sequences into train/val/test splits
Handles temporal data for LSTM training

Usage:
    # Process collected data into splits
    python m3_data_pipeline.py --process

    # Review dataset statistics
    python m3_data_pipeline.py --stats
"""

import os
import json
import pickle
from pathlib import Path
from typing import Tuple, Dict, List
import numpy as np
from sklearn.model_selection import train_test_split


class DataPipeline:
    """Process raw keypoint sequences into ML-ready datasets."""

    def __init__(self, raw_dir: str = "data/raw", processed_dir: str = "data/processed"):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def load_sequences(self) -> Tuple[List[np.ndarray], List[str], List[str]]:
        """Load all keypoint sequences from raw directory."""
        sequences = []
        labels = []
        sessions = []

        for npy_file in sorted(self.raw_dir.glob("*.npy")):
            # Parse filename: LABEL_SESSION_NUM.npy
            parts = npy_file.stem.split("_")
            if len(parts) >= 3:
                label = parts[0]
                session = "_".join(parts[1:-1])

                seq = np.load(npy_file)
                sequences.append(seq)
                labels.append(label)
                sessions.append(session)

        return sequences, labels, sessions

    def create_splits(self, test_size: float = 0.2, val_size: float = 0.1,
                     random_state: int = 42) -> Dict:
        """Create train/val/test splits by session (avoid leakage)."""
        sequences, labels, sessions = self.load_sequences()

        if not sequences:
            print("No sequences found in", self.raw_dir)
            return {}

        # Group by session
        session_data = {}
        for seq, label, session in zip(sequences, labels, sessions):
            if session not in session_data:
                session_data[session] = []
            session_data[session].append((seq, label))

        # Split sessions (not frames)
        unique_sessions = list(session_data.keys())
        train_sessions, temp_sessions = train_test_split(
            unique_sessions, test_size=test_size + val_size,
            random_state=random_state
        )
        val_sessions, test_sessions = train_test_split(
            temp_sessions, test_size=test_size/(test_size+val_size),
            random_state=random_state
        )

        splits = {
            'train': [],
            'val': [],
            'test': []
        }

        for session in train_sessions:
            splits['train'].extend(session_data[session])
        for session in val_sessions:
            splits['val'].extend(session_data[session])
        for session in test_sessions:
            splits['test'].extend(session_data[session])

        return splits

    def save_splits(self, splits: Dict):
        """Save splits to disk as pickle files."""
        for split_name, data in splits.items():
            if not data:
                continue

            sequences = [seq for seq, _ in data]
            labels = [label for _, label in data]

            filepath = self.processed_dir / f"{split_name}.pkl"
            with open(filepath, 'wb') as f:
                pickle.dump({'sequences': sequences, 'labels': labels}, f)

            print(f"Saved {split_name}: {len(sequences)} sequences")

    def process_all(self):
        """Full pipeline: load → split → save."""
        print("Processing sequences...")
        splits = self.create_splits()
        self.save_splits(splits)
        print("✓ Data pipeline complete")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="M3: Data Pipeline")
    parser.add_argument("--process", action="store_true", help="Process data into splits")
    parser.add_argument("--stats", action="store_true", help="Show dataset stats")
    args = parser.parse_args()

    pipeline = DataPipeline()

    if args.process:
        pipeline.process_all()
    elif args.stats:
        sequences, labels, sessions = pipeline.load_sequences()
        print(f"Total sequences: {len(sequences)}")
        print(f"Unique labels: {set(labels)}")
        print(f"Unique sessions: {set(sessions)}")
        if sequences:
            print(f"Sequence shape: {sequences[0].shape}")


if __name__ == "__main__":
    main()
