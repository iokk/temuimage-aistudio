FROM python:3.12-slim-bookworm

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY apps/worker ./apps/worker

CMD ["python", "-m", "celery", "-A", "apps.worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
