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
        self.assertIn("异步执行后端", workspace_text)
        self.assertIn("fallback_reason", workspace_text)
        self.assertIn("persistence_ready", workspace_text)
        self.assertIn("execution_fallback_reason", workspace_text)
        self.assertIn("execution_queue_ready", workspace_text)
        self.assertIn("execution_storage_compatible", workspace_text)

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
        self.assertIn("requireSignedIn", page_text)

    def test_admin_page_uses_runtime_panel(self):
        admin_text = Path("apps/web/app/admin/page.tsx").read_text()
        panel_text = Path("apps/web/components/admin-runtime-panel.tsx").read_text()
        system_text = Path("apps/api/routers/system.py").read_text()
        self.assertIn("AdminRuntimePanel", admin_text)
        self.assertIn("getRuntimePayload", panel_text)
        self.assertIn("getReadinessPayload", panel_text)
        self.assertIn('@router.get("/runtime")', system_text)
        self.assertIn('@router.get("/readiness")', system_text)
        self.assertIn("异步执行", panel_text)

    def test_task_detail_page_exists_and_reads_job(self):
        detail_text = Path("apps/web/app/tasks/[jobId]/page.tsx").read_text()
        self.assertIn("getServerJob", detail_text)
        self.assertIn("requireSignedIn", detail_text)
        self.assertIn("TaskDetailView", detail_text)

    def test_task_detail_view_supports_live_refresh(self):
        detail_view_text = Path("apps/web/components/task-detail-view.tsx").read_text()
        self.assertIn("最近更新时间", detail_view_text)
        self.assertIn("updated_at", detail_view_text)
        self.assertIn("setInterval", detail_view_text)
        self.assertIn("StructuredResult", detail_view_text)
        self.assertIn("状态时间线", detail_view_text)
        self.assertIn("job.history.map", detail_view_text)

    def test_tasks_workspace_links_to_detail_page(self):
        workspace_text = Path("apps/web/components/tasks-workspace.tsx").read_text()
        self.assertIn("href={`/tasks/${item.id}`}", workspace_text)

    def test_title_and_translate_workspaces_create_jobs(self):
        title_text = Path("apps/web/components/title-workspace.tsx").read_text()
        translate_text = Path("apps/web/components/translate-workspace.tsx").read_text()
        self.assertIn("submitAsyncJob", title_text)
        self.assertIn("waitForJobCompletion", title_text)
        self.assertIn('task_type: "title_generation"', title_text)
        self.assertIn("submitAsyncJob", translate_text)
        self.assertIn("waitForJobCompletion", translate_text)
        self.assertIn('task_type: "image_translate"', translate_text)

    def test_job_client_supports_async_lifecycle(self):
        client_text = Path("apps/web/lib/job-client.ts").read_text()
        self.assertIn("submitAsyncJob", client_text)
        self.assertIn("waitForJobCompletion", client_text)
        self.assertIn("getJob", client_text)
        self.assertIn("/submit-async", client_text)
        self.assertIn("/status", client_text)


if __name__ == "__main__":
    unittest.main()
