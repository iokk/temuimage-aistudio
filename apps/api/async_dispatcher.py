from __future__ import annotations

from threading import Thread
import os

from apps.api.job_repository import job_repository
from apps.api.task_processor import process_task_preview
from apps.worker.celery_app import celery_app


_preferred_backend = (
    os.getenv("ASYNC_JOB_BACKEND", "inline").strip().lower() or "inline"
)
_active_backend = _preferred_backend
_fallback_reason = ""


def _is_celery_storage_compatible() -> bool:
    storage_meta = job_repository.get_backend_meta()
    return bool(storage_meta.get("persistence_ready"))


def _process_inline(job_id: str, task_type: str, payload: dict):
    try:
        job_repository.update_job(job_id, status="running")
        result = process_task_preview(task_type, payload)
        job_repository.update_job(job_id, status="completed", result=result)
    except Exception as exc:  # pragma: no cover - defensive background path
        job_repository.update_job(
            job_id,
            status="failed",
            result={"error": str(exc)},
        )


def get_async_backend_meta() -> dict[str, str | bool]:
    compatible = _preferred_backend != "celery" or _is_celery_storage_compatible()
    return {
        "active_execution_backend": _active_backend,
        "preferred_execution_backend": _preferred_backend,
        "execution_fallback_reason": _fallback_reason,
        "execution_queue_ready": _active_backend == "celery",
        "execution_storage_compatible": compatible,
    }


def dispatch_preview_job(job_id: str, task_type: str, payload: dict) -> str:
    global _active_backend, _fallback_reason

    backend = _preferred_backend

    if backend == "celery":
        if not _is_celery_storage_compatible():
            _active_backend = "inline"
            _fallback_reason = (
                "Celery 需要持久化任务存储；请先将 JOB_STORE_BACKEND 切到 database。"
            )
        else:
            try:
                celery_app.send_task(
                    "jobs.process_preview", args=[job_id, task_type, payload]
                )
                _active_backend = "celery"
                _fallback_reason = ""
                return "celery"
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive broker fallback path
                _active_backend = "inline"
                _fallback_reason = str(exc)

    Thread(
        target=_process_inline, args=(job_id, task_type, payload), daemon=True
    ).start()
    if backend != "celery":
        _active_backend = "inline"
        _fallback_reason = ""
    return "inline"
