from celery import Celery
import os

from apps.api.job_repository import job_repository
from apps.api.task_processor import process_task_preview


celery_app = Celery(
    "xiaobaitu_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_app.task(name="health.ping")
def ping_task():
    return {"status": "ok"}


@celery_app.task(name="jobs.process_preview")
def process_preview_job(job_id: str, task_type: str, payload: dict):
    try:
        job_repository.update_job(job_id, status="running")
        result = process_task_preview(task_type, payload)
        job_repository.update_job(job_id, status="completed", result=result)
        return {
            "job_id": job_id,
            "task_type": task_type,
            "status": "completed",
        }
    except Exception as exc:
        job_repository.update_job(
            job_id,
            status="failed",
            result={"error": str(exc)},
        )
        raise
