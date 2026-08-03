FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-web.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-web.txt

COPY app.py .
COPY task_engine.py .
COPY task_store.py .
COPY task_status.py .
COPY suite_planner.py .
COPY suite_output.py .
COPY run_tulite.py .
COPY provider_acceptance.py .
COPY scripts/verify_provider.py ./scripts/verify_provider.py
COPY .streamlit/ ./.streamlit/

ENV APP_RUNTIME=server
ENV ECOMMERCE_WORKBENCH_DATA_DIR=/app/data
ENV ECOMMERCE_WORKBENCH_PROJECTS_DIR=/app/data/projects
ENV FILE_STORAGE_PATH=/app/data/files

RUN mkdir -p /app/data /app/data/files /app/data/projects

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["python", "run_tulite.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
