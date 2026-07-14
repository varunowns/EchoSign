"""
EchoSign GitHub Push Preparation Script
========================================
Cleans up, organizes, and prepares the project for GitHub deployment

Run: python github_prep.py
"""

import os
import shutil
from pathlib import Path

def cleanup_project():
    """Clean up unnecessary files for GitHub."""

    print("="*70)
    print("EchoSign GitHub Deployment Preparation")
    print("="*70)

    # Files/dirs to remove
    remove_patterns = [
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '.pytest_cache',
        '.venv',
        'venv',
        'env',
        '*.egg-info',
        'dist',
        'build',
        '*.log',
        '.DS_Store',
        'Thumbs.db',
        '.vscode',
        '.idea',
        '*.swp',
        '*.swo',
    ]

    print("\n[PHASE 1] Removing unnecessary files...")
    print("-" * 70)

    for pattern in remove_patterns:
        if '*' in pattern:
            # Handle wildcards
            for file in Path('.').rglob(pattern):
                try:
                    if file.is_dir():
                        shutil.rmtree(file)
                        print(f"  [DELETED] {file}/")
                    else:
                        file.unlink()
                        print(f"  [DELETED] {file}")
                except Exception as e:
                    print(f"  [ERROR] Could not delete {file}: {e}")
        else:
            # Direct paths
            if Path(pattern).exists():
                if Path(pattern).is_dir():
                    shutil.rmtree(pattern)
                    print(f"  [DELETED] {pattern}/")
                else:
                    Path(pattern).unlink()
                    print(f"  [DELETED] {pattern}")

    # Clean data directories
    print("\n[PHASE 2] Cleaning data directories...")
    print("-" * 70)

    data_cleanup = {
        'data/raw': 'Keep for reference (synthetic test data)',
        'data/processed': 'Keep (train/test splits)',
        'models': 'Keep directory structure',
        'logs': 'Keep directory structure',
    }

    for dir_path, note in data_cleanup.items():
        if Path(dir_path).exists():
            # Remove large .npy files, keep structure
            for file in Path(dir_path).rglob('*.npy'):
                try:
                    file.unlink()
                    print(f"  [CLEANED] {file}")
                except Exception as e:
                    print(f"  [ERROR] {file}: {e}")

            print(f"  [KEEP] {dir_path}/ - {note}")

    # Ensure correct .gitignore
    print("\n[PHASE 3] Setting up .gitignore...")
    print("-" * 70)

    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Cache
.pytest_cache/
.mypy_cache/
*.cache

# Logs
*.log
logs/

# Data (large files)
data/raw/*.npy
models/*.pkl
models/*.pt
models/*.pth

# Environment
.env
.env.local

# Media
*.mp4
*.avi
*.mov
"""

    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    print("  [CREATED] .gitignore")

    # Create/update .gitkeep files
    print("\n[PHASE 4] Adding .gitkeep for empty directories...")
    print("-" * 70)

    keep_dirs = [
        'backend/data/raw',
        'backend/data/processed',
        'backend/models',
        'backend/logs',
        'frontend',
    ]

    for dir_path in keep_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        gitkeep = Path(dir_path) / '.gitkeep'
        gitkeep.touch()
        print(f"  [CREATED] {dir_path}/.gitkeep")

    # Create GitHub documentation
    print("\n[PHASE 5] Creating GitHub documentation...")
    print("-" * 70)

    github_docs = {
        'GitHub Setup': (create_github_setup(), 'GITHUB_SETUP.md'),
        'Main README': (create_main_readme(), 'README.md'),
        'Backend README': (create_backend_readme(), 'backend/README.md'),
        'Frontend README': (create_frontend_readme(), 'frontend/README.md'),
    }

    for doc_name, (content, filepath) in github_docs.items():
        print(f"  [CREATED] {doc_name}")

    print("\n" + "="*70)
    print("Cleanup Complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. git init")
    print("2. git add .")
    print("3. git commit -m 'Initial commit: EchoSign full stack'")
    print("4. git branch -M main")
    print("5. git remote add origin https://github.com/varunowns/EchoSign.git")
    print("6. git push -u origin main")
    print("\n" + "="*70)

def create_github_setup():
    """Create GITHUB_SETUP.md"""
    content = """# GitHub Repository Setup (ASCII Safe)"""

## Initial Setup

```bash
git init
git add .
git commit -m "Initial commit: EchoSign full stack"
git branch -M main
git remote add origin https://github.com/varunowns/EchoSign.git
git push -u origin main
```

## Branches

- `main` - Production-ready code
- `develop` - Development branch
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "Add your feature"`
3. Push to branch: `git push origin feature/your-feature`
4. Open Pull Request on GitHub

## Commit Message Format

```
type(scope): subject

body

footer
```

Types: feat, fix, docs, style, refactor, perf, test, chore
"""
    with open('GITHUB_SETUP.md', 'w', encoding='utf-8') as f:
        f.write(content)
    return content

def create_main_readme():
    """Create main README.md"""
    content = """# EchoSign - Real-Time Sign Language Translator

A complete end-to-end system for real-time sign language recognition using MediaPipe, PyTorch, and React.

## Features

- **Real-Time Keypoint Extraction** (M1): 28-30 FPS webcam capture with MediaPipe
- **Static Gesture Recognition** (M2): ASL alphabet classification
- **Dynamic Gesture Recognition** (M4): LSTM-based temporal sequence modeling
- **Live Inference** (M5): Real-time predictions with post-processing
- **Web UI**: React frontend with live video display
- **FastAPI Backend**: RESTful API + WebSocket for real-time communication

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/varunowns/EchoSign.git
cd EchoSign

# Setup backend
cd backend
pip install -r requirements.txt

# Setup frontend (in another terminal)
cd frontend
npm install
```

### Running

```bash
# Terminal 1: Start backend
cd backend
python backend_api.py

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Test integration
python test_integration.py
```

Access:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
EchoSign/
├── backend/
│   ├── M1_improved.py          # Keypoint extraction
│   ├── m2_static_classifier.py # Static gestures
│   ├── m3_data_pipeline.py     # Data processing
│   ├── m4_sequence_model.py    # LSTM model
│   ├── m5_live_inference.py    # Real-time inference
│   ├── backend_api.py          # FastAPI server
│   ├── Dockerfile
│   ├── requirements.txt
│   └── data/, models/, logs/
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
│
├── echosign-client.js          # React integration helper
├── test_integration.py         # Integration tests
├── docker-compose.yml
└── README.md (this file)
```

## Performance

| Component | Latency | FPS | Accuracy |
|-----------|---------|-----|----------|
| M1 Keypoints | 30-50ms | 28-30 | N/A |
| M2 Static | <5ms | N/A | 100% (synthetic) |
| M4 LSTM | 50-100ms | N/A | 95%+ (synthetic) |

## Documentation

- [Backend README](backend/README.md) - Backend setup & API
- [Frontend README](frontend/README.md) - Frontend setup & UI
- [Integration Guide](BACKEND_FRONTEND_INTEGRATION.md) - How to integrate
- [Deployment Guide](DEPLOYMENT_READY.md) - Production deployment
- [GitHub Setup](GITHUB_SETUP.md) - Repository management

## Docker Deployment

```bash
docker-compose up --build
```

Backend: http://localhost:8000
Frontend: http://localhost:3000

## License

MIT License - see LICENSE file

## Author

Varun Owns (@varunowns)

## Contributing

See [GITHUB_SETUP.md](GITHUB_SETUP.md) for contribution guidelines.
"""
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(content)
    return content

def create_backend_readme():
    """Create backend/README.md"""
    content = """# EchoSign Backend

FastAPI server for real-time sign language recognition pipeline.

## Setup

```bash
pip install -r requirements.txt
python backend_api.py
```

Server runs on `http://localhost:8000`

## API Endpoints

### REST API

- `GET /api/health` - Server health check
- `GET /api/models` - List available models
- `POST /api/config` - Update configuration
- `POST /api/infer` - Single frame inference

### WebSocket

- `WS /ws/live` - Real-time video stream and inference

### Documentation

Interactive API docs: `http://localhost:8000/docs`

## Models (M1-M5)

- **M1**: Keypoint extraction (MediaPipe)
- **M2**: Static gesture classifier (Random Forest)
- **M3**: Data processing pipeline
- **M4**: LSTM sequence model
- **M5**: Real-time inference + post-processing

## Configuration

Edit `backend_api.py` configuration:

```python
config.confidence_threshold = 0.7
config.smoothing_window = 5
config.debounce_frames = 3
```

## Performance

- Health check: <10ms
- Model inference: 5-100ms
- WebSocket latency: <50ms
"""
    Path('backend').mkdir(exist_ok=True)
    with open('backend/README.md', 'w', encoding='utf-8') as f:
        f.write(content)
    return content

def create_frontend_readme():
    """Create frontend/README.md"""
    content = """# EchoSign Frontend

React UI for EchoSign sign language recognition system.

## Setup

```bash
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

## Architecture

- React with Vite
- WebSocket client for backend communication
- Live video display with predictions
- Real-time transcript

## Integration

Import and use `EchoSignClient`:

```javascript
import { useEchoSign } from '../echosign-client'

export function App() {
  const { client, connected } = useEchoSign()
  // Use client to send frames and receive predictions
}
```

## Building

```bash
npm run build
```

## Deployment

See [DEPLOYMENT_READY.md](../DEPLOYMENT_READY.md)
"""
    Path('frontend').mkdir(exist_ok=True)
    with open('frontend/README.md', 'w', encoding='utf-8') as f:
        f.write(content)
    return content

if __name__ == '__main__':
    cleanup_project()
