from __future__ import annotations

from pathlib import Path
import unittest


class RebuildQuickFlowTest(unittest.TestCase):
    def test_api_router_exists_and_exposes_preview(self):
        router_text = Path("apps/api/routers/quick.py").read_text()
        self.assertIn('@router.post("/preview")', router_text)
        self.assertIn('@router.get("/meta")', router_text)
        self.assertIn(
            'DEFAULT_TITLE_MODEL = "gemini-3.1-flash-lite-preview"', router_text
        )

    def test_api_main_includes_quick_router(self):
        main_text = Path("apps/api/main.py").read_text()
        self.assertIn("quick_router", main_text)
        self.assertIn("include_router(quick_router)", main_text)

    def test_quick_page_uses_workspace_component_and_guard(self):
        page_text = Path("apps/web/app/quick/page.tsx").read_text()
        self.assertIn("QuickWorkspace", page_text)
        self.assertIn("requireSignedIn", page_text)

    def test_quick_workspace_creates_task_center_job(self):
        workspace_text = Path("apps/web/components/quick-workspace.tsx").read_text()
        self.assertIn("submitAsyncJob", workspace_text)
        self.assertIn("waitForJobCompletion", workspace_text)
        self.assertIn('task_type: "quick_generation"', workspace_text)


if __name__ == "__main__":
    unittest.main()
