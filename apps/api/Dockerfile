FROM python:3.12-slim-bookworm

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY temu_core ./temu_core

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
