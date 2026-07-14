#!/bin/bash
# Quick Start Script for EchoSign Backend-Frontend Integration
# Run: bash setup.sh

set -e

echo "=========================================="
echo "EchoSign Backend-Frontend Setup"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Reorganize project structure
echo -e "${BLUE}[Step 1] Reorganizing project structure...${NC}"
python reorganize_fixed.py

# Step 2: Install backend dependencies
echo -e "${BLUE}[Step 2] Installing backend dependencies...${NC}"
cd backend
pip install -r requirements.txt
cd ..

# Step 3: Clone frontend if not exists
if [ ! -d "frontend" ]; then
    echo -e "${BLUE}[Step 3] Cloning frontend repository...${NC}"
    git clone https://github.com/varunowns/ui_for_EchoSign frontend
fi

# Step 4: Install frontend dependencies
echo -e "${BLUE}[Step 4] Installing frontend dependencies...${NC}"
cd frontend
npm install
cd ..

echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Terminal 1: cd backend && python backend_api.py"
echo "2. Terminal 2: cd frontend && npm run dev"
echo "3. Terminal 3: python test_integration.py"
echo ""
echo "Frontend will be at: http://localhost:3000"
echo "Backend API at: http://localhost:8000"
echo "API Docs at: http://localhost:8000/docs"
