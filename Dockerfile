FROM python:3.12-slim-bookworm

WORKDIR /app

# 安装系统依赖（Debian 12 Bookworm 兼容）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（使用最新pip）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/data/files

# 暴露端口
EXPOSE 8501

# 健康检查（兼容平台动态 PORT）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD sh -c 'curl --fail http://localhost:${PORT:-8501}/_stcore/health || exit 1'

# 启动命令（兼容平台动态 PORT）
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
