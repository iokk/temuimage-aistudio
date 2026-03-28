from __future__ import annotations

from pathlib import Path
import unittest


class RebuildTranslateFlowTest(unittest.TestCase):
    def test_api_router_exists_and_exposes_preview(self):
        router_text = Path("apps/api/routers/translate.py").read_text()
        self.assertIn('@router.post("/preview")', router_text)
        self.assertIn('@router.get("/meta")', router_text)
        self.assertIn("describe_capability_reasons", router_text)

    def test_api_main_includes_translate_router(self):
        main_text = Path("apps/api/main.py").read_text()
        self.assertIn("translate_router", main_text)
        self.assertIn("include_router(translate_router)", main_text)

    def test_translate_page_uses_workspace_component_and_guard(self):
        page_text = Path("apps/web/app/translate/page.tsx").read_text()
        self.assertIn("TranslateWorkspace", page_text)
        self.assertIn("requireSignedIn", page_text)

    def test_translate_workspace_uses_async_job_flow_and_shows_capability_hint(self):
        workspace_text = Path("apps/web/components/translate-workspace.tsx").read_text()
        self.assertIn("submitAsyncJob", workspace_text)
        self.assertIn("waitForJobCompletion", workspace_text)
        self.assertIn('task_type: "image_translate"', workspace_text)
        self.assertIn("是否支持图片翻译出图", workspace_text)
        self.assertIn("生成翻译预览", workspace_text)


if __name__ == "__main__":
    unittest.main()
