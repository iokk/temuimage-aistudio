from __future__ import annotations

from pathlib import Path
import unittest


class RebuildQuickFlowTest(unittest.TestCase):
    def test_api_router_exists_and_exposes_preview(self):
        router_text = Path("apps/api/routers/quick.py").read_text()
        self.assertIn('@router.post("/preview")', router_text)
        self.assertIn('@router.get("/meta")', router_text)
        self.assertIn(
            'DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"', router_text
        )
        self.assertIn('DEFAULT_TITLE_MODEL = "gemini-3.1-pro"', router_text)

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
        client_text = Path("apps/web/lib/job-client.ts").read_text()
        self.assertIn("submitAsyncJob", workspace_text)
        self.assertIn("waitForJobCompletion", workspace_text)
        self.assertIn('task_type: "quick_generation"', workspace_text)
        self.assertIn("生成快速出图", workspace_text)
        self.assertIn("artifact_data_url", workspace_text)
        self.assertIn("商品图片上传（1-6 张）", workspace_text)
        self.assertIn("卖点图", workspace_text)
        self.assertIn("场景图", workspace_text)
        self.assertIn("细节图", workspace_text)
        self.assertIn("对比图", workspace_text)
        self.assertIn("规格图", workspace_text)
        self.assertIn("buildJobArtifactsZipUrl", workspace_text)
        self.assertIn("导出 ZIP", workspace_text)
        self.assertIn("下载 PNG", workspace_text)
        self.assertIn("ImageUploadItem", client_text)


if __name__ == "__main__":
    unittest.main()
