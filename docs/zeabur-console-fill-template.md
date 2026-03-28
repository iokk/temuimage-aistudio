# Zeabur 控制台逐项填写模板

这份文档按 **Zeabur 控制台实际操作顺序** 写，尽量做到可以直接照抄。

## 一、模板入口

- 仓库：`iokk/temuimage-aistudio`
- 分支：`main`
- 模板文件：`template.yaml`

## 二、创建模板时需要填写的变量

### 1. `WEB_DOMAIN`

- 含义：前端站点域名
- 填写示例：`studio.example.com`

### 2. `API_DOMAIN`

- 含义：API 域名
- 填写示例：`api.example.com`

### 3. `NEXTAUTH_SECRET`

- 含义：NextAuth / Auth.js 会话签名密钥
- 必填：是
- 填写方式：32 位以上随机字符串
- 填写示例：`请使用 scripts/generate_zeabur_env.py 生成`

### 4. `CASDOOR_ISSUER`

- 含义：Casdoor OIDC Issuer 地址
- 必填：是
- 填写示例：`https://casdoor.example.com`

### 5. `CASDOOR_CLIENT_ID`

- 含义：Casdoor 应用 Client ID
- 必填：是

### 6. `CASDOOR_CLIENT_SECRET`

- 含义：Casdoor 应用 Client Secret
- 必填：是

### 7. `TEAM_ADMIN_EMAILS`

- 含义：团队管理员邮箱
- 必填：建议是
- 填写格式：逗号分隔
- 填写示例：`admin@example.com,ops@example.com`

### 8. `TEAM_ALLOWED_EMAIL_DOMAINS`

- 含义：允许进入团队模式的邮箱域名
- 必填：建议是
- 填写格式：逗号分隔
- 填写示例：`example.com`

### 9. `SYSTEM_ENCRYPTION_KEY`

- 含义：后端系统加密密钥
- 必填：是
- 填写方式：32 字节以上随机字符串
- 填写示例：`请使用 scripts/generate_zeabur_env.py 生成`

## 三、模板自动创建的服务

创建模板后，Zeabur 会自动创建：

- `postgresql`
- `redis`
- `api`
- `worker`
- `web`

## 四、模板会自动注入的变量

下面这些不用你手动填，模板会自动接：

- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `AUTO_BOOTSTRAP_DB=true`（仅 `api`）
- `NEXT_PUBLIC_API_BASE_URL=https://${API_DOMAIN}`
- `NEXTAUTH_URL=https://${WEB_DOMAIN}`

## 五、Zeabur 控制台逐项检查

### `postgresql`

- 状态应为 Running
- 能看到连接串暴露变量

### `redis`

- 状态应为 Running
- 能看到 `REDIS_CONNECTION_STRING`

### `api`

- Dockerfile：`apps/api/Dockerfile`
- 端口：`8000`
- 必须看到：
  - `DATABASE_URL`
  - `REDIS_URL`
  - `JOB_STORE_BACKEND=database`
  - `ASYNC_JOB_BACKEND=celery`
  - `AUTO_BOOTSTRAP_DB=true`

### `worker`

- Dockerfile：`apps/worker/Dockerfile`
- 必须看到：
  - `DATABASE_URL`
  - `REDIS_URL`
  - `JOB_STORE_BACKEND=database`
  - `ASYNC_JOB_BACKEND=celery`
  - `AUTO_BOOTSTRAP_DB=false`

### `web`

- Dockerfile：`apps/web/Dockerfile`
- 端口：`3000`
- 必须看到：
  - `NEXT_PUBLIC_API_BASE_URL`
  - `NEXTAUTH_URL`
  - `NEXTAUTH_SECRET`

## 六、数据库初始化

首次部署时，不需要额外手动执行数据库初始化命令。

只要 `api` 服务里是：

- `AUTO_BOOTSTRAP_DB=true`

它首次启动时会自动：

- 创建 FastAPI 当前需要的 SQLAlchemy 表
- seed `system@xiaobaitu.local`

只有在你后续发布包含 Prisma migration 的版本时，才需要额外执行：

```bash
pnpm deploy:db
```

## 七、发布 smoke 检查

```bash
API_BASE_URL=https://你的API域名 WEB_BASE_URL=https://你的前端域名 ./scripts/zeabur_rebuild_release.sh
```

## 八、上线通过标准

打开 `https://你的前端域名/admin` 后，必须确认：

- `Readiness = ready`
- `active_backend = database`
- `active_execution_backend = celery`
- 没有 blocking warnings

## 九、推荐做法

- 先运行 `python3 scripts/generate_zeabur_env.py`
- 把生成结果复制到 Zeabur 控制台
- 再创建模板和服务
