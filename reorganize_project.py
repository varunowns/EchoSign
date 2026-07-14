"""
Reorganize EchoSign project structure:
- Move all Python/MediaPipe code to backend/
- Keep documentation at root
- Prepare for frontend/ integration
"""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(".")
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Files to move to backend
PYTHON_FILES = [
    "M1.py", "M1_improved.py",
    "data_collector.py", "m2_static_classifier.py", "m3_data_pipeline.py",
    "m4_sequence_model.py", "m5_live_inference.py",
    "run_pipeline.py", "synthetic_data_gen.py", "test_m2_m5.py"
]

MODEL_FILES = [
    "hand_landmarker.task", "pose_landmarker.task"
]

DIRECTORIES = [
    "data", "models", "logs"
]

# Ensure backend/frontend exist
BACKEND_DIR.mkdir(exist_ok=True)
FRONTEND_DIR.mkdir(exist_ok=True)

print("Moving Python files to backend/...")
for file in PYTHON_FILES:
    src = PROJECT_ROOT / file
    dst = BACKEND_DIR / file
    if src.exists():
        shutil.move(str(src), str(dst))
        print(f"  [OK] {file}")

print("\nMoving MediaPipe models to backend/...")
for file in MODEL_FILES:
    src = PROJECT_ROOT / file
    dst = BACKEND_DIR / file
    if src.exists():
        shutil.move(str(src), str(dst))
        print(f"  [OK] {file}")

print("\nMoving data directories to backend/...")
for dir_name in DIRECTORIES:
    src = PROJECT_ROOT / dir_name
    dst = BACKEND_DIR / dir_name
    if src.exists():
        shutil.move(str(src), str(dst))
        print(f"  [OK] {dir_name}/")

print("\n[SUCCESS] Project reorganization complete!")
print("\nNew structure:")
print("V:\\EchoSign/")
print("├── backend/")
print("│   ├── *.py (all Python code)")
print("│   ├── *.task (MediaPipe models)")
print("│   ├── data/")
print("│   ├── models/")
print("│   └── logs/")
print("├── frontend/")
print("│   └── (UI code goes here)")
print("└── *.md (documentation)")
