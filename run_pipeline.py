"""
EchoSign M2-M5 Integrated Pipeline Orchestrator
================================================
End-to-end runner that coordinates all stages:
M2 (train classifier) → M3 (process data) → M4 (train LSTM) → M5 (live inference)

Usage:
    python run_pipeline.py --generate-data         # Generate synthetic data for testing
    python run_pipeline.py --train-m2              # Train M2 static classifier
    python run_pipeline.py --train-m4              # Train M4 sequence model (requires M3 data)
    python run_pipeline.py --infer                 # Run M5 live inference
    python run_pipeline.py --full-test             # Generate data → Train M2 → Run inference
"""

import argparse
import subprocess
import sys
from pathlib import Path
import time


class EchoSignPipeline:
    """Orchestrator for M2-M5 pipeline."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / "data" / "raw"
        self.processed_dir = self.project_root / "data" / "processed"
        self.models_dir = self.project_root / "models"

    def run_command(self, script: str, args: list = None) -> bool:
        """Run a Python script and return success status."""
        cmd = ["python", str(self.project_root / script)]
        if args:
            cmd.extend(args)

        print(f"\n{'='*60}")
        print(f"Running: {' '.join(cmd)}")
        print(f"{'='*60}\n")

        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode == 0
        except Exception as e:
            print(f"ERROR: {e}")
            return False

    def generate_synthetic_data(self, num_samples: int = 10):
        """M2: Generate synthetic training data."""
        print("\n🔄 PHASE 1: Generating Synthetic Data")
        print("This creates realistic synthetic keypoint sequences for all 26 letters")

        return self.run_command(
            "synthetic_data_gen.py",
            ["--num-samples", str(num_samples), "--output-dir", str(self.data_dir)]
        )

    def train_m2(self):
        """M2: Train static gesture classifier."""
        print("\n🔄 PHASE 2: Training M2 Static Classifier")
        print("Training Random Forest on frame-wise features from 26 ASL letters")

        # Check if data exists
        if not list(self.data_dir.glob("*.npy")):
            print("ERROR: No training data found in", self.data_dir)
            print("Run --generate-data first")
            return False

        return self.run_command("m2_static_classifier.py", ["--train"])

    def process_m3_data(self):
        """M3: Process collected data into train/val/test splits."""
        print("\n🔄 PHASE 3: Processing M3 Data into Splits")
        print("Creating train/val/test splits stratified by session")

        return self.run_command("m3_data_pipeline.py", ["--process"])

    def train_m4(self):
        """M4: Train LSTM sequence model."""
        print("\n🔄 PHASE 4: Training M4 LSTM Model")
        print("Training LSTM on temporal keypoint sequences")

        # Check if processed data exists
        if not self.processed_dir.exists():
            print("ERROR: Processed data not found")
            print("Run --train-m3 first")
            return False

        return self.run_command("m4_sequence_model.py", ["--train"])

    def run_m5_inference(self):
        """M5: Run real-time inference pipeline."""
        print("\n🔄 PHASE 5: Running M5 Live Inference")
        print("Real-time gesture recognition from webcam")
        print("Press q to quit, SPACE to pause, c to clear transcript")

        model_path = self.models_dir / "sequence_model.pt"
        args = ["--model", str(model_path)] if model_path.exists() else []

        return self.run_command("m5_live_inference.py", args)

    def run_full_pipeline(self):
        """Run full M2-M5 pipeline with synthetic data."""
        print("\n" + "="*60)
        print("EchoSign M2-M5 Full Pipeline")
        print("="*60)

        # Phase 1: Generate data
        if not self.generate_synthetic_data(num_samples=20):
            print("\n❌ Data generation failed")
            return False

        # Phase 2: Train M2
        if not self.train_m2():
            print("\n❌ M2 training failed")
            return False

        print("\n✓ M2 training complete - ASL alphabet classifier ready")
        print("\nNow you can:")
        print("  - Run live inference: python run_pipeline.py --infer")
        print("  - Collect real data and train M4: python data_collector.py")
        print("  - Process data and train LSTM: python run_pipeline.py --train-m4")

        return True

    def main(self):
        """Parse arguments and run pipeline."""
        parser = argparse.ArgumentParser(
            description="EchoSign M2-M5 Pipeline Orchestrator"
        )
        parser.add_argument("--generate-data", action="store_true",
                           help="Generate synthetic training data")
        parser.add_argument("--num-samples", type=int, default=10,
                           help="Samples per letter for synthetic data")
        parser.add_argument("--train-m2", action="store_true",
                           help="Train M2 static classifier")
        parser.add_argument("--train-m3", action="store_true",
                           help="Process M3 data into splits")
        parser.add_argument("--train-m4", action="store_true",
                           help="Train M4 LSTM model")
        parser.add_argument("--infer", action="store_true",
                           help="Run M5 live inference")
        parser.add_argument("--full-test", action="store_true",
                           help="Run full pipeline (generate → train)")

        args = parser.parse_args()

        if args.full_test:
            success = self.run_full_pipeline()
        elif args.generate_data:
            success = self.generate_synthetic_data(args.num_samples)
        elif args.train_m2:
            success = self.train_m2()
        elif args.train_m3:
            success = self.process_m3_data()
        elif args.train_m4:
            success = self.train_m4()
        elif args.infer:
            success = self.run_m5_inference()
        else:
            parser.print_help()
            return 0

        return 0 if success else 1


if __name__ == "__main__":
    orchestrator = EchoSignPipeline()
    sys.exit(orchestrator.main())
