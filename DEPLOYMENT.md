# TEMU AI Studio V1.0.0 部署清单

## 1. 本地检查

```bash
python3 -m py_compile app.py
bash -n scripts/deploy-zeabur.sh
bash -n scripts/deploy-debian.sh
```

## 2. Zeabur 模板化部署（推荐）

仓库根目录已提供 `template.yaml`，推荐优先用模板化方式部署，而不是裸 GitHub Import。

### 模板化部署会自动拉起

1. `temu-app`
2. `postgresql`
3. `redis`

并自动注入：

```bash
DATABASE_URL=${POSTGRES_CONNECTION_STRING}
REDIS_URL=${REDIS_CONNECTION_STRING}
PLATFORM_AUTO_MIGRATE=true
PLATFORM_SEED_DEFAULTS=true
PLATFORM_DEFAULT_ORG_NAME=TEMU Team Workspace
PLATFORM_DEFAULT_PROJECT_NAME=Default Project
TITLE_TEXT_MODEL=gemini-3.1-pro
```

### 首次只需填写

```bash
SYSTEM_API_KEYS_FIXED=你的 Gemini Key
ADMIN_PASSWORD_FIXED=你的管理员密码
PLATFORM_ENCRYPTION_KEY=高强度随机值
PUBLIC_DOMAIN=可选域名
```

### 说明

- `Deploy Button` 需要你先在 Zeabur 后台基于 `template.yaml` 创建一次模板条目
- 创建后你就可以把按钮回填到 `README.md`

## 3. GitHub → Zeabur 部署（备用）

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

## 4. 原生服务器部署

```bash
./scripts/deploy-debian.sh install
```

## 5. 健康检查

```bash
curl http://localhost:8501/_stcore/health
```

## 5.1 上线后验证

部署完成后，建议按这份清单快速验证：

`docs/post-deploy-checklist.md`

## 6. 常见问题

- `FAILED_PRECONDITION`：优先改走 Vertex Express / Vertex AI 区域端点
- 长时间出图慢：降低图片并发，优先 `minimal`
- 服务卡在 `STARTING`：优先检查服务器容器运行层，而不是先怀疑代码
- 登录页提示团队数据库未就绪：优先检查 `DATABASE_URL`、数据库连通性，以及是否缺表/未迁移
