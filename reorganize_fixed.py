"""
Reorganize EchoSign project structure - Fixed Unicode version
Move all Python/MediaPipe code to backend/ folder
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
    "run_pipeline.py", "synthetic_data_gen.py", "test_m2_m5.py",
    "backend_api.py", "reorganize_project.py"
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

print("=" * 60)
print("Moving Python files to backend/...")
print("=" * 60)
for file in PYTHON_FILES:
    src = PROJECT_ROOT / file
    dst = BACKEND_DIR / file
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        print("[OK] {}".format(file))
    elif dst.exists():
        print("[SKIP] {} (already exists)".format(file))

print("\n" + "=" * 60)
print("Moving MediaPipe models to backend/...")
print("=" * 60)
for file in MODEL_FILES:
    src = PROJECT_ROOT / file
    dst = BACKEND_DIR / file
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        print("[OK] {}".format(file))
    elif dst.exists():
        print("[SKIP] {} (already exists)".format(file))

print("\n" + "=" * 60)
print("Moving data directories to backend/...")
print("=" * 60)
for dir_name in DIRECTORIES:
    src = PROJECT_ROOT / dir_name
    dst = BACKEND_DIR / dir_name
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        print("[OK] {}/".format(dir_name))
    elif dst.exists():
        print("[SKIP] {}/ (already exists)".format(dir_name))

print("\n" + "=" * 60)
print("[SUCCESS] Project reorganization complete!")
print("=" * 60)
print("\nNew structure:")
print("V:\\EchoSign/")
print("|-- backend/")
print("|   |-- *.py (all Python code)")
print("|   |-- *.task (MediaPipe models)")
print("|   |-- data/")
print("|   |-- models/")
print("|   |-- logs/")
print("|   `-- requirements.txt")
print("|")
print("|-- frontend/")
print("|   `-- (UI code cloned here)")
print("|")
print("|-- *.md (documentation)")
print("`-- echosign-client.js (frontend helper)")
print("\nNext steps:")
print("1. cd backend && pip install -r requirements.txt")
print("2. python backend_api.py")
print("3. cd frontend && npm install && npm run dev")
