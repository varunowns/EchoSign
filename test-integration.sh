#!/bin/bash
echo "[*] Testing Frontend-Backend Integration"
echo

# Test 1: Backend health
echo "Test 1: Backend Health"
curl -s http://localhost:8000/api/health | python -m json.tool
echo

# Test 2: Frontend loads
echo "Test 2: Frontend Loads"
curl -s http://localhost:3000 | grep -o "EchoSign" | head -1 && echo "[OK] Frontend HTML contains EchoSign" || echo "[X] Frontend not responding"
echo

# Test 3: Frontend has API client
echo "Test 3: API Client Library"
test -f frontend/lib/api.ts && echo "[OK] API client created" || echo "[X] API client missing"
test -f frontend/hooks/useBackendInference.ts && echo "[OK] Backend hook created" || echo "[X] Backend hook missing"
test -f frontend/.env.local && echo "[OK] Env config created" || echo "[X] Env config missing"
echo

echo "[OK] Integration test complete"
