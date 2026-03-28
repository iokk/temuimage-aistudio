from __future__ import annotations

import unittest

TestClient = None
app = None

try:
    from fastapi.testclient import TestClient

    from apps.api.main import app

    FASTAPI_TESTS_AVAILABLE = True
except ModuleNotFoundError:
    FASTAPI_TESTS_AVAILABLE = False


@unittest.skipUnless(FASTAPI_TESTS_AVAILABLE, "fastapi test dependencies unavailable")
class APISkeletonTest(unittest.TestCase):
    def setUp(self):
        assert FASTAPI_TESTS_AVAILABLE
        assert TestClient is not None
        assert app is not None
        self.client = TestClient(app)  # type: ignore[arg-type]

    def test_root_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_versioned_system_health(self):
        response = self.client.get("/v1/system/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "api")

    def test_versioned_system_runtime(self):
        response = self.client.get("/v1/system/runtime")
        self.assertEqual(response.status_code, 200)
        self.assertIn("warnings", response.json())
        self.assertIn("ready_for_distributed_workers", response.json())

    def test_versioned_system_readiness(self):
        response = self.client.get("/v1/system/readiness")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())
        self.assertIn("blocking_warnings", response.json())

    def test_versioned_jobs_meta(self):
        response = self.client.get("/v1/jobs/meta")
        self.assertEqual(response.status_code, 200)
        self.assertIn("task_types", response.json())


if __name__ == "__main__":
    unittest.main()
