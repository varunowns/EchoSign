"""
Synthetic Data Generator for Testing
=====================================
Generates realistic synthetic keypoint sequences for testing M2-M5
without needing to record actual data

Usage:
    python synthetic_data_gen.py --num-samples 20 --output-dir data/raw
"""

import numpy as np
from pathlib import Path
import argparse
import json


def generate_synthetic_keypoint_sequence(label: str, num_frames: int = 45) -> np.ndarray:
    """
    Generate synthetic keypoint sequence for a letter.

    Each letter gets a unique "pattern" in the feature space:
    - A: hands high, far apart
    - B: hands close, moving
    - etc.
    """
    np.random.seed(hash(label) % 2**32)  # Deterministic per label

    # Start with neutral pose
    seq = np.zeros((num_frames, 300))

    # Pose block (33 landmarks × 4 channels)
    pose_base = np.random.randn(33, 4) * 0.1
    pose_base[:, 3] = 0.9  # visibility

    # Left hand base (21 landmarks × 4)
    left_hand_base = np.random.randn(21, 4) * 0.15
    left_hand_base[:, 3] = 0.85  # confidence

    # Right hand base (21 landmarks × 4)
    right_hand_base = np.random.randn(21, 4) * 0.15
    right_hand_base[:, 3] = 0.85

    # Letter-specific patterns
    letter_patterns = {
        'A': {'left_offset': [0.3, 0.2], 'right_offset': [-0.3, 0.2], 'hand_dist': 0.6},
        'B': {'left_offset': [0.0, 0.0], 'right_offset': [0.1, 0.0], 'hand_dist': 0.1},
        'C': {'left_offset': [-0.2, 0.0], 'right_offset': [0.2, 0.0], 'hand_dist': 0.4},
        'D': {'left_offset': [0.1, 0.1], 'right_offset': [-0.1, 0.1], 'hand_dist': 0.2},
        'E': {'left_offset': [0.2, -0.2], 'right_offset': [-0.2, -0.2], 'hand_dist': 0.4},
        'F': {'left_offset': [0.15, 0.3], 'right_offset': [-0.15, 0.0], 'hand_dist': 0.3},
        'G': {'left_offset': [0.25, 0.1], 'right_offset': [-0.25, 0.15], 'hand_dist': 0.5},
        'H': {'left_offset': [0.2, 0.0], 'right_offset': [-0.2, 0.0], 'hand_dist': 0.4},
        'I': {'left_offset': [0.0, 0.3], 'right_offset': [0.05, 0.3], 'hand_dist': 0.05},
        'J': {'left_offset': [0.1, 0.2], 'right_offset': [0.1, 0.35], 'hand_dist': 0.15},
        'K': {'left_offset': [0.2, 0.15], 'right_offset': [-0.2, 0.0], 'hand_dist': 0.4},
        'L': {'left_offset': [0.1, 0.2], 'right_offset': [-0.1, -0.1], 'hand_dist': 0.3},
        'M': {'left_offset': [0.3, 0.0], 'right_offset': [-0.3, 0.0], 'hand_dist': 0.6},
        'N': {'left_offset': [0.2, 0.1], 'right_offset': [-0.2, -0.1], 'hand_dist': 0.4},
        'O': {'left_offset': [0.15, 0.2], 'right_offset': [-0.15, 0.2], 'hand_dist': 0.3},
        'P': {'left_offset': [0.1, 0.25], 'right_offset': [0.0, 0.0], 'hand_dist': 0.1},
        'Q': {'left_offset': [0.2, 0.1], 'right_offset': [-0.2, -0.1], 'hand_dist': 0.4},
        'R': {'left_offset': [0.15, 0.2], 'right_offset': [-0.15, 0.1], 'hand_dist': 0.3},
        'S': {'left_offset': [0.05, 0.1], 'right_offset': [-0.05, 0.1], 'hand_dist': 0.1},
        'T': {'left_offset': [0.1, 0.25], 'right_offset': [-0.1, 0.25], 'hand_dist': 0.2},
        'U': {'left_offset': [0.2, 0.0], 'right_offset': [-0.2, 0.0], 'hand_dist': 0.4},
        'V': {'left_offset': [0.25, 0.1], 'right_offset': [-0.25, 0.1], 'hand_dist': 0.5},
        'W': {'left_offset': [0.3, 0.05], 'right_offset': [-0.3, 0.05], 'hand_dist': 0.6},
        'X': {'left_offset': [0.1, 0.15], 'right_offset': [-0.1, 0.15], 'hand_dist': 0.2},
        'Y': {'left_offset': [0.2, 0.3], 'right_offset': [-0.2, 0.0], 'hand_dist': 0.4},
        'Z': {'left_offset': [0.2, 0.2], 'right_offset': [-0.2, -0.2], 'hand_dist': 0.4},
    }

    pattern = letter_patterns.get(label, {'left_offset': [0, 0], 'right_offset': [0, 0], 'hand_dist': 0.3})

    # Generate temporal sequence with motion
    for frame_idx in range(num_frames):
        t = frame_idx / num_frames  # 0 to 1

        # Pose (normalized)
        seq[frame_idx, :132] = pose_base.flatten()

        # Left hand with letter-specific offset
        left_hand = left_hand_base.copy()
        left_hand[:5, 0] += pattern['left_offset'][0] + 0.1 * np.sin(2 * np.pi * t)  # x
        left_hand[:5, 1] += pattern['left_offset'][1] + 0.1 * np.cos(2 * np.pi * t)  # y
        seq[frame_idx, 132:216] = left_hand.flatten()

        # Right hand
        right_hand = right_hand_base.copy()
        right_hand[:5, 0] += pattern['right_offset'][0] + 0.1 * np.sin(2 * np.pi * t)
        right_hand[:5, 1] += pattern['right_offset'][1] + 0.1 * np.cos(2 * np.pi * t)
        seq[frame_idx, 216:300] = right_hand.flatten()

        # Add some noise
        seq[frame_idx] += np.random.randn(300) * 0.02

    return seq


def generate_dataset(letters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    num_samples_per_letter: int = 5,
                    output_dir: str = "data/raw") -> None:
    """Generate complete synthetic dataset."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Generating synthetic data for {len(letters)} letters, {num_samples_per_letter} samples each...")

    session_id = "synthetic_001"
    total = 0

    for letter in letters:
        for sample_idx in range(num_samples_per_letter):
            seq = generate_synthetic_keypoint_sequence(letter, num_frames=45)

            # Save keypoint sequence
            filename = f"{letter}_{session_id}_{sample_idx+1:03d}.npy"
            filepath = Path(output_dir) / filename
            np.save(filepath, seq)

            # Save metadata
            metadata = {
                "label": letter,
                "num_frames": seq.shape[0],
                "synthetic": True,
                "session": session_id,
            }
            metadata_file = Path(output_dir) / filename.replace(".npy", ".json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)

            total += 1

    print(f"✓ Generated {total} synthetic sequences in {output_dir}")
    print(f"  Ready for M2 training: python m2_static_classifier.py --train")


def main():
    parser = argparse.ArgumentParser(description="Synthetic Data Generator")
    parser.add_argument("--num-samples", type=int, default=5,
                       help="Samples per letter")
    parser.add_argument("--letters", default="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                       help="Letters to generate")
    parser.add_argument("--output-dir", default="data/raw",
                       help="Output directory")
    args = parser.parse_args()

    generate_dataset(args.letters, args.num_samples, args.output_dir)


if __name__ == "__main__":
    main()
