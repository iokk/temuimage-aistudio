from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from apps.api.main import app


class APISkeletonTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_versioned_system_health(self):
        response = self.client.get("/v1/system/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "api")

    def test_versioned_jobs_meta(self):
        response = self.client.get("/v1/jobs/meta")
        self.assertEqual(response.status_code, 200)
        self.assertIn("task_types", response.json())


if __name__ == "__main__":
    unittest.main()
