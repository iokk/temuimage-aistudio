from celery import Celery
import os


celery_app = Celery(
    "xiaobaitu_worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_app.task(name="health.ping")
def ping_task():
    return {"status": "ok"}
