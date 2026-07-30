# 1Panel Docker 部署

这个目录只部署 Web 版，不包含 `desktop/` 或 `desktop-app/`。

## 1Panel 使用方式

1. 在服务器创建目录，例如 `/opt/1panel/apps/xiaobaitu-web/xiaobaitu-web/`。
2. 上传完整仓库作为 Docker 构建上下文。Web 镜像至少会从仓库中复制：
   - `app.py`
   - `task_engine.py`
   - `task_store.py`
   - `task_status.py`
   - `run_tulite.py`
   - `provider_acceptance.py`
   - `Dockerfile.web`
   - `requirements-web.txt`
   - `scripts/verify_provider.py`
   - `.streamlit/`
   - `deploy/1panel/docker-compose.yml`
   - `deploy/1panel/.env.example`
3. 在 `deploy/1panel/` 下复制环境文件：

   ```bash
   cp .env.example .env
   ```

4. 在 `.env` 中生成并填写你自己的高强度随机 `APP_ACCESS_PASSWORD`，并设置有效的 Fernet
   `XIAOBAITU_SECRET_KEY`，再填写 `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`，并按需修改 `APP_PORT`。
   环境变量 Key 会保留在 `.env` 中且不会复制到 `providers.json`；请把 `.env` 权限设为 600，并确保它不进入仓库或公开备份。
5. 在 1Panel 的“容器 / Compose”中选择 `deploy/1panel/docker-compose.yml` 创建应用。

如果你用 1Panel 的网站反向代理：

- 代理目标填 `http://127.0.0.1:8501`
- 开启 WebSocket
- 域名启用 HTTPS 后再公开访问

默认只允许服务器本机访问：

- `http://127.0.0.1:8501`
- 健康检查：`http://127.0.0.1:8501/_stcore/health`

推荐通过 1Panel 反向代理公开服务。只有在已设置高强度访问口令、且明确需要直接 IP 访问时，才把 `APP_BIND_ADDRESS` 改为 `0.0.0.0` 并开放防火墙端口。

## Demo 模式

生产部署默认关闭：

```env
XIAOBAITU_DEMO_MODE=0
```

如果只是给面试官体验，可以临时改为：

```env
XIAOBAITU_DEMO_MODE=1
```

Demo 模式会显示测试密钥入口，并用本地演示结果跑通流程，不会访问外部 AI API。
