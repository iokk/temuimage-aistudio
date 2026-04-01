from __future__ import annotations

from pathlib import Path
import unittest


class RebuildTitleFlowTest(unittest.TestCase):
    def test_api_router_exposes_real_title_context_contract(self):
        router_text = Path("apps/api/routers/title.py").read_text()
        self.assertIn('@router.get("/context")', router_text)
        self.assertIn("get_effective_execution_config_for_user", router_text)
        self.assertIn("_resolve_title_provider", router_text)
        self.assertIn("list_title_template_options", router_text)
        self.assertIn('"default_template_key": DEFAULT_TITLE_TEMPLATE_KEY', router_text)
        self.assertIn('"image_template_key": IMAGE_TITLE_TEMPLATE_KEY', router_text)
        self.assertIn('"ready": not blocking_reason', router_text)
        self.assertIn('"blocking_reason": blocking_reason or None', router_text)

    def test_api_main_includes_title_router(self):
        main_text = Path("apps/api/main.py").read_text()
        self.assertIn("title_router", main_text)
        self.assertIn("include_router(title_router)", main_text)

    def test_title_page_uses_workspace_component_and_guard(self):
        page_text = Path("apps/web/app/title/page.tsx").read_text()
        server_api_text = Path("apps/web/lib/server-api.ts").read_text()
        runtime_text = Path("apps/web/lib/runtime.ts").read_text()
        self.assertIn("TitleWorkspace", page_text)
        self.assertIn("requireSignedIn", page_text)
        self.assertIn("getServerTitleContext", page_text)
        self.assertIn("default_template_key", runtime_text)
        self.assertIn("template_options", runtime_text)
        self.assertIn('config_source: "unavailable"', server_api_text)
        self.assertIn('default_template_key: "default"', server_api_text)
        self.assertIn('image_template_key: "image_analysis"', server_api_text)
        self.assertIn("标题执行上下文获取失败", server_api_text)

    def test_title_workspace_uses_async_job_flow_and_bilingual_review(self):
        workspace_text = Path("apps/web/components/title-workspace.tsx").read_text()
        review_text = Path("apps/web/components/title-review-results.tsx").read_text()
        self.assertIn("submitAsyncJob", workspace_text)
        self.assertIn("waitForJobCompletion", workspace_text)
        self.assertIn('task_type: "title_generation"', workspace_text)
        self.assertIn("生成标题", workspace_text)
        self.assertIn("标题执行状态", workspace_text)
        self.assertIn("config_source", workspace_text)
        self.assertIn("blocking_reason", workspace_text)
        self.assertIn("请先修复标题配置", workspace_text)
        self.assertIn("!titleContext || !titleContext.ready", workspace_text)
        self.assertIn("标题执行上下文尚未就绪", workspace_text)
        self.assertIn("selectedTemplateKey", workspace_text)
        self.assertIn("templateKey: selectedTemplateKey", workspace_text)
        self.assertIn("TitleReviewResults", workspace_text)
        self.assertIn("标题模板", workspace_text)
        self.assertIn("合规模式", workspace_text)
        self.assertIn("titlePairsSource={result.title_pairs}", workspace_text)
        self.assertIn("buildCopyAllValue", review_text)
        self.assertIn("英文标题", review_text)
        self.assertIn("中文标题", review_text)
        self.assertIn("成对复制输出", review_text)


if __name__ == "__main__":
    unittest.main()
