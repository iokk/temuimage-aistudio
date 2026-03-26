from __future__ import annotations

import unittest

import app


class PlatformDeployDiagnosticsTest(unittest.TestCase):
    def test_missing_database_url_status_message(self):
        status = {
            "configured": False,
            "reachable": False,
            "missing_tables": [],
            "error": "",
        }
        info = app.describe_platform_database_status(status)
        self.assertEqual(info["state"], "missing_database_url")
        self.assertIn("DATABASE_URL", info["message"])

    def test_unreachable_database_status_message(self):
        status = {
            "configured": True,
            "reachable": False,
            "missing_tables": [],
            "error": "could not connect",
        }
        info = app.describe_platform_database_status(status)
        self.assertEqual(info["state"], "database_unreachable")
        self.assertIn("could not connect", info["detail"])

    def test_missing_tables_status_message(self):
        status = {
            "configured": True,
            "reachable": True,
            "missing_tables": ["users", "organizations"],
            "error": "",
        }
        info = app.describe_platform_database_status(status)
        self.assertEqual(info["state"], "missing_tables")
        self.assertIn("users", info["detail"])

    def test_ready_status_message(self):
        status = {
            "configured": True,
            "reachable": True,
            "missing_tables": [],
            "error": "",
            "dialect": "postgresql",
            "table_count": 15,
        }
        info = app.describe_platform_database_status(status)
        self.assertEqual(info["state"], "ready")
        self.assertIn("postgresql", info["message"])


if __name__ == "__main__":
    unittest.main()
