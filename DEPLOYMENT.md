# TEMU AI Studio V1.0.0 部署清单

## 1. 本地检查

```bash
python3 -m py_compile app.py
bash -n scripts/deploy-zeabur.sh
bash -n scripts/deploy-debian.sh
```

## 2. GitHub → Zeabur 部署

推荐用于持续更新。

### 步骤

1. 将代码推送到 GitHub
2. 在 Zeabur 中连接仓库
3. 配置环境变量
4. 等待构建并验证健康检查

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
