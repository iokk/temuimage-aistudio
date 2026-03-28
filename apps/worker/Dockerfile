FROM python:3.12-slim-bookworm

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY temu_core ./temu_core

CMD ["python", "-m", "celery", "-A", "apps.worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
