"""
Backend-Frontend Integration Test
==================================
Verify FastAPI backend + frontend connection

Run after:
1. python backend_api.py (in terminal 1)
2. npm run dev (in terminal 2, frontend folder)
3. python test_integration.py (in terminal 3)
"""

import requests
import asyncio
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

class IntegrationTester:
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0

    def test(self, name, func):
        """Run a test and track results."""
        print(f"\n[TEST] {name}")
        try:
            result = func()
            if result:
                print(f"  [PASS] {name}")
                self.tests_passed += 1
            else:
                print(f"  [FAIL] {name}")
                self.tests_failed += 1
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            self.tests_failed += 1

    def test_health(self):
        """Test /api/health endpoint."""
        response = requests.get(f"{BASE_URL}/api/health")
        return response.status_code == 200

    def test_models_endpoint(self):
        """Test /api/models endpoint."""
        response = requests.get(f"{BASE_URL}/api/models")
        data = response.json()
        return "m1" in data and "m2" in data and "m4" in data and "m5" in data

    def test_config_update(self):
        """Test /api/config endpoint."""
        new_config = {
            "confidence_threshold": 0.8,
            "smoothing_window": 7
        }
        response = requests.post(
            f"{BASE_URL}/api/config",
            json=new_config
        )
        return response.status_code == 200

    def test_frontend_accessible(self):
        """Test if frontend is running."""
        try:
            response = requests.get("http://localhost:3000", timeout=2)
            return response.status_code == 200
        except:
            print("    (Frontend not yet running on :3000)")
            return False

    def run_all(self):
        """Run all tests."""
        print("=" * 60)
        print("EchoSign Integration Test Suite")
        print("=" * 60)

        print("\n[PHASE] Backend API Tests")
        print("-" * 60)
        self.test("Backend health check", self.test_health)
        self.test("Models endpoint", self.test_models_endpoint)
        self.test("Config update", self.test_config_update)

        print("\n[PHASE] Frontend Tests")
        print("-" * 60)
        self.test("Frontend accessible", self.test_frontend_accessible)

        print("\n" + "=" * 60)
        print(f"Results: {self.tests_passed} passed, {self.tests_failed} failed")
        print("=" * 60)

        if self.tests_failed == 0:
            print("\n[SUCCESS] All tests passed!")
            print("\nNext: Connect frontend to backend via WebSocket")
            print("  1. Import echosign-client.js in frontend")
            print("  2. Use useEchoSign() hook in React components")
            print("  3. Send frames via client.sendFrame(canvas)")
        else:
            print("\n[FAILURES] Fix issues above before proceeding")

        return self.tests_failed == 0


def main():
    print("Waiting for backend... (make sure backend_api.py is running)")
    print("Starting tests in 2 seconds...")

    import time
    time.sleep(2)

    tester = IntegrationTester()
    success = tester.run_all()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
