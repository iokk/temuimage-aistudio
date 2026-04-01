from __future__ import annotations

from pathlib import Path
import unittest


class RebuildTaskCenterTest(unittest.TestCase):
    def test_jobs_router_exposes_submit_and_list(self):
        router_text = Path("apps/api/routers/jobs.py").read_text()
        self.assertIn('@router.get("/list")', router_text)
        self.assertIn('@router.post("/submit")', router_text)
        self.assertIn('@router.post("/submit-async")', router_text)
        self.assertIn('@router.get("/{job_id}")', router_text)
        self.assertIn('@router.post("/{job_id}/status")', router_text)
        self.assertIn('@router.get("/{job_id}/translate-export.zip")', router_text)
        self.assertIn("dispatch_preview_job", router_text)
        self.assertIn("get_backend_meta", router_text)
        self.assertIn("get_async_backend_meta", router_text)

    def test_job_repository_contains_title_and_translate_meta(self):
        store_text = Path("apps/api/job_repository.py").read_text()
        self.assertIn('"title_generation"', store_text)
        self.assertIn('"image_translate"', store_text)
        self.assertIn('"batch_generation"', store_text)
        self.assertIn('"quick_generation"', store_text)
        self.assertIn('TIMELINE_KEY = "_timeline"', store_text)

    def test_job_repository_supports_database_backend_toggle(self):
        store_text = Path("apps/api/job_repository.py").read_text()
        env_text = Path(".env.rebuild.example").read_text()
        self.assertIn("JOB_STORE_BACKEND", store_text)
        self.assertIn("SqlAlchemyJobRepository", store_text)
        self.assertIn("ResilientJobRepository", store_text)
        self.assertIn("JOB_STORE_BACKEND=memory", env_text)

    def test_tasks_workspace_shows_backend_state(self):
        workspace_text = Path("apps/web/components/tasks-workspace.tsx").read_text()
        self.assertIn("任务存储后端", workspace_text)
        self.assertIn("当前项目", workspace_text)
        self.assertIn("全部任务", workspace_text)
        self.assertIn("project_id=", workspace_text)
        self.assertIn("异步执行后端", workspace_text)
        self.assertIn("fallback_reason", workspace_text)
        self.assertIn("persistence_ready", workspace_text)
        self.assertIn("execution_fallback_reason", workspace_text)
        self.assertIn("execution_queue_ready", workspace_text)
        self.assertIn("execution_storage_compatible", workspace_text)

    def test_app_shell_shows_global_current_project_context(self):
        shell_text = Path("apps/web/components/app-shell.tsx").read_text()
        self.assertIn("getServerRuntimePayload", shell_text)
        self.assertIn("const runtime = await getServerRuntimePayload()", shell_text)
        self.assertIn(
            "const currentProject = runtime?.current_project || null", shell_text
        )
        self.assertIn(
            "const currentProjectText = currentProject",
            shell_text,
        )
        self.assertIn("currentProject.project_name", shell_text)
        self.assertIn("currentProject.project_slug", shell_text)
        self.assertIn('"当前项目：未设置"', shell_text)
        self.assertIn("Project context", shell_text)
        self.assertIn("xl:hidden", shell_text)

    def test_async_dispatcher_supports_backend_metadata(self):
        dispatcher_text = Path("apps/api/async_dispatcher.py").read_text()
        env_text = Path(".env.rebuild.example").read_text()
        self.assertIn("get_async_backend_meta", dispatcher_text)
        self.assertIn("_is_celery_storage_compatible", dispatcher_text)
        self.assertIn(
            "JOB_STORE_BACKEND", Path("apps/api/async_dispatcher.py").read_text()
        )
        self.assertIn("ASYNC_JOB_BACKEND", dispatcher_text)
        self.assertIn("ASYNC_JOB_BACKEND=inline", env_text)

    def test_tasks_page_uses_workspace_component(self):
        page_text = Path("apps/web/app/tasks/page.tsx").read_text()
        self.assertIn("TasksWorkspace", page_text)
        self.assertIn("getServerRuntimePayload", page_text)
        self.assertIn("currentProject=", page_text)
        self.assertIn("requireSignedIn", page_text)

    def test_workspace_pages_pass_current_project_from_runtime(self):
        for path, component_name in [
            ("apps/web/app/title/page.tsx", "TitleWorkspace"),
            ("apps/web/app/translate/page.tsx", "TranslateWorkspace"),
            ("apps/web/app/quick/page.tsx", "QuickWorkspace"),
            ("apps/web/app/batch/page.tsx", "BatchWorkspace"),
        ]:
            page_text = Path(path).read_text()
            self.assertIn(component_name, page_text)
            self.assertIn("getServerRuntimePayload", page_text)
            self.assertIn("const runtime = await getServerRuntimePayload()", page_text)
            self.assertIn(
                "currentProject={runtime?.current_project || null}", page_text
            )

    def test_admin_page_uses_runtime_panel(self):
        admin_text = Path("apps/web/app/admin/page.tsx").read_text()
        panel_text = Path("apps/web/components/admin-runtime-panel.tsx").read_text()
        system_text = Path("apps/api/routers/system.py").read_text()
        self.assertIn("AdminRuntimePanel", admin_text)
        self.assertIn("getRuntimePayload", panel_text)
        self.assertIn("getReadinessPayload", panel_text)
        self.assertIn("AdminConfigPanel", panel_text)
        self.assertIn('@router.get("/runtime")', system_text)
        self.assertIn('@router.get("/readiness")', system_text)
        self.assertIn('@router.get("/config")', system_text)
        self.assertIn('@router.put("/config")', system_text)
        self.assertIn("异步执行", panel_text)

    def test_task_detail_page_exists_and_reads_job(self):
        detail_text = Path("apps/web/app/tasks/[jobId]/page.tsx").read_text()
        self.assertIn("getServerJob", detail_text)
        self.assertIn("requireSignedIn", detail_text)
        self.assertIn("TaskDetailView", detail_text)
        self.assertIn('subtitle="任务详情"', detail_text)

    def test_task_detail_view_supports_live_refresh(self):
        detail_view_text = Path("apps/web/components/task-detail-view.tsx").read_text()
        title_review_text = Path(
            "apps/web/components/title-review-results.tsx"
        ).read_text()
        self.assertIn("最近更新时间", detail_view_text)
        self.assertIn("所属项目", detail_view_text)
        self.assertIn("返回任务中心", detail_view_text)
        self.assertIn("返回该项目的", detail_view_text)
        self.assertIn("updated_at", detail_view_text)
        self.assertIn("setInterval", detail_view_text)
        self.assertIn("StructuredResult", detail_view_text)
        self.assertIn("OutputCard", detail_view_text)
        self.assertIn("BatchAnchorCard", detail_view_text)
        self.assertIn("artifact_data_url", detail_view_text)
        self.assertIn("TranslateImageBatchResult", detail_view_text)
        self.assertIn("buildJobArtifactsZipUrl", detail_view_text)
        self.assertIn("buildTranslateOutputsZipUrl", detail_view_text)
        self.assertIn("下载当前 PNG", detail_view_text)
        self.assertIn("导出 ZIP", detail_view_text)
        self.assertIn("状态时间线", detail_view_text)
        self.assertIn("job.history.map", detail_view_text)
        self.assertIn("执行来源：", detail_view_text)
        self.assertIn("Tokens：", detail_view_text)
        self.assertIn("配置来源：", detail_view_text)
        self.assertIn("TitleReviewResults", detail_view_text)
        self.assertIn("标题模板：", detail_view_text)
        self.assertIn("合规模式：", detail_view_text)
        self.assertIn("titlePairsSource={result.title_pairs}", detail_view_text)
        self.assertIn("成对复制输出", title_review_text)

    def test_tasks_workspace_links_to_detail_page(self):
        workspace_text = Path("apps/web/components/tasks-workspace.tsx").read_text()
        self.assertIn("href={`/tasks/${item.id}`}", workspace_text)

    def test_title_and_translate_workspaces_create_jobs(self):
        title_text = Path("apps/web/components/title-workspace.tsx").read_text()
        translate_text = Path("apps/web/components/translate-workspace.tsx").read_text()
        client_text = Path("apps/web/lib/job-client.ts").read_text()
        self.assertIn("submitAsyncJob", title_text)
        self.assertIn("waitForJobCompletion", title_text)
        self.assertIn('task_type: "title_generation"', title_text)
        self.assertIn("已写入{taskCenterLabel}", title_text)
        self.assertIn("taskCenterLinkLabel", title_text)
        self.assertIn("请到{taskCenterLabel}查看最新状态", title_text)
        self.assertIn("标题执行状态", title_text)
        self.assertIn("请先修复标题配置", title_text)
        self.assertIn("配置来源：", title_text)
        self.assertIn("标题模板", title_text)
        self.assertIn("templateKey: selectedTemplateKey", title_text)
        self.assertIn("TitleReviewResults", title_text)
        self.assertIn("submitAsyncJob", translate_text)
        self.assertIn("waitForJobCompletion", translate_text)
        self.assertIn('task_type: "image_translate"', translate_text)
        self.assertIn("已写入{taskCenterLabel}", translate_text)
        self.assertIn("taskCenterLinkLabel", translate_text)
        self.assertIn("提交 OCR 文本或图片后", translate_text)
        self.assertIn("uploadItems", translate_text)
        self.assertIn("重试失败图片", translate_text)
        self.assertIn("导出 ZIP", translate_text)
        self.assertIn("下载当前 PNG", translate_text)
        self.assertIn("buildTranslateOutputsZipUrl", client_text)
        self.assertIn("translate-export.zip", client_text)

    def test_workspace_components_show_current_project_context(self):
        for path in [
            "apps/web/components/title-workspace.tsx",
            "apps/web/components/translate-workspace.tsx",
            "apps/web/components/quick-workspace.tsx",
            "apps/web/components/batch-workspace.tsx",
        ]:
            workspace_text = Path(path).read_text()
            self.assertIn(
                'currentProject?: RuntimePayload["current_project"]', workspace_text
            )
            self.assertIn("当前项目：", workspace_text)
            self.assertIn("服务端会在提交时继续校验项目上下文", workspace_text)

    def test_quick_and_batch_workspaces_use_project_aware_task_center_copy(self):
        quick_text = Path("apps/web/components/quick-workspace.tsx").read_text()
        batch_text = Path("apps/web/components/batch-workspace.tsx").read_text()
        self.assertIn("已写入{taskCenterLabel}", quick_text)
        self.assertIn("taskCenterLinkLabel", quick_text)
        self.assertIn("查看任务进度和最终结果", quick_text)
        self.assertIn("商品图片上传（1-6 张）", quick_text)
        self.assertIn("导出 ZIP", quick_text)
        self.assertIn("已写入{taskCenterLabel}", batch_text)
        self.assertIn("taskCenterLinkLabel", batch_text)
        self.assertIn("继续查看任务进度", batch_text)
        self.assertIn("商品图片上传（1-6 张）", batch_text)
        self.assertIn("批次锚点摘要", batch_text)
        self.assertIn("导出 ZIP", batch_text)

    def test_tasks_workspace_uses_project_scope_copy(self):
        workspace_text = Path("apps/web/components/tasks-workspace.tsx").read_text()
        self.assertIn("taskCenterTitle", workspace_text)
        self.assertIn("当前仅显示该项目任务", workspace_text)
        self.assertIn("正在加载当前项目任务", workspace_text)
        self.assertIn("当前项目下还没有任务", workspace_text)

    def test_job_client_supports_async_lifecycle(self):
        client_text = Path("apps/web/lib/job-client.ts").read_text()
        proxy_text = Path("apps/web/app/api/platform/[...path]/route.ts").read_text()
        self.assertIn("project_name", client_text)
        self.assertIn("project_slug", client_text)
        self.assertIn("submitAsyncJob", client_text)
        self.assertIn("waitForJobCompletion", client_text)
        self.assertIn("getJob", client_text)
        self.assertIn("ImageUploadItem", client_text)
        self.assertIn("buildJobArtifactsZipUrl", client_text)
        self.assertIn("artifacts.zip", client_text)
        self.assertIn("/submit-async", client_text)
        self.assertIn("/status", client_text)
        self.assertIn("export async function PUT", proxy_text)


if __name__ == "__main__":
    unittest.main()
