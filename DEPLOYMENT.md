# TEMU AI Studio V1.0.0 部署清单

## 1. 本地检查

```bash
python3 -m py_compile app.py
bash -n scripts/deploy-zeabur.sh
bash -n scripts/deploy-debian.sh
```

## 2. GitHub → Zeabur 部署

推荐用于持续更新。

### 团队版新增基础设施

长期团队版建议同时接入：

1. Zeabur 托管 PostgreSQL
2. Zeabur 托管 Redis
3. S3 / OSS / COS / MinIO 对象存储

核心环境变量：

```bash
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
PLATFORM_AUTO_MIGRATE=true
PLATFORM_SEED_DEFAULTS=true
PLATFORM_DEFAULT_ORG_NAME=TEMU Team Workspace
PLATFORM_DEFAULT_PROJECT_NAME=Default Project
PLATFORM_ENCRYPTION_KEY=请设置高强度随机值
TITLE_TEXT_MODEL=gemini-3.1-pro
```

说明：

- `PLATFORM_ENCRYPTION_KEY` 建议在 Zeabur 生产环境必填，用于加密保存系统 API Key
- 团队数据库启用后，普通用户通过注册账号登录；共享密码只保留给回退场景和管理员引导

### 步骤

1. 将代码推送到 GitHub
2. 在 Zeabur 中连接仓库
3. 配置环境变量
4. 等待构建并验证健康检查
5. 进入管理后台，确认 `Team Wallet Foundation` 状态为 ready

### 推荐环境变量

```bash
SYSTEM_API_KEYS_FIXED=AQ.xxxxx
SYSTEM_API_KEYS_SYNC_MODE=replace
GOOGLE_GENAI_USE_VERTEXAI=true
ADMIN_PASSWORD_FIXED=你的管理员密码
USER_PASSWORD_FIXED=你的用户密码
ALLOW_PASSWORDLESS_USER_LOGIN=true
PORT=8501
```

## 3. 原生服务器部署

```bash
./scripts/deploy-debian.sh install
```

## 4. 健康检查

```bash
curl http://localhost:8501/_stcore/health
```

## 5. 常见问题

- `FAILED_PRECONDITION`：优先改走 Vertex Express / Vertex AI 区域端点
- 长时间出图慢：降低图片并发，优先 `minimal`
- 服务卡在 `STARTING`：优先检查服务器容器运行层，而不是先怀疑代码
- 团队账本未初始化：确认 `DATABASE_URL` 已配置，并执行 `python3 -m alembic upgrade head`
