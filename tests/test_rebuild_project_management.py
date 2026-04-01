from __future__ import annotations

from pathlib import Path
import unittest


class RebuildProjectManagementTest(unittest.TestCase):
    def test_main_registers_projects_router(self):
        main_text = Path("apps/api/main.py").read_text()
        self.assertIn("projects_router", main_text)
        self.assertIn("api_v1.include_router(projects_router)", main_text)

    def test_projects_router_exposes_current_project_endpoints(self):
        router_text = Path("apps/api/routers/projects.py").read_text()
        self.assertIn('prefix="/projects"', router_text)
        self.assertIn('@router.get("")', router_text)
        self.assertIn('@router.post("")', router_text)
        self.assertIn('@router.get("/current")', router_text)
        self.assertIn('@router.put("/current")', router_text)
        self.assertIn('@router.put("/current/select")', router_text)
        self.assertIn("require_team_member", router_text)
        self.assertIn("require_admin", router_text)


if __name__ == "__main__":
    unittest.main()
