from __future__ import annotations

from pathlib import Path
import unittest


class RebuildTitleFlowTest(unittest.TestCase):
    def test_api_router_exists_and_uses_expected_model_name(self):
        router_text = Path("apps/api/routers/title.py").read_text()
        self.assertIn('DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"', router_text)
        self.assertIn('@router.post("/preview")', router_text)
        self.assertIn('@router.get("/meta")', router_text)

    def test_api_main_includes_title_router(self):
        main_text = Path("apps/api/main.py").read_text()
        self.assertIn("title_router", main_text)
        self.assertIn("include_router(title_router)", main_text)

    def test_title_page_uses_workspace_component_and_guard(self):
        page_text = Path("apps/web/app/title/page.tsx").read_text()
        self.assertIn("TitleWorkspace", page_text)
        self.assertIn("requireSignedIn", page_text)

    def test_title_workspace_uses_async_job_flow(self):
        workspace_text = Path("apps/web/components/title-workspace.tsx").read_text()
        self.assertIn("submitAsyncJob", workspace_text)
        self.assertIn("waitForJobCompletion", workspace_text)
        self.assertIn('task_type: "title_generation"', workspace_text)
        self.assertIn("生成标题预览", workspace_text)


if __name__ == "__main__":
    unittest.main()
