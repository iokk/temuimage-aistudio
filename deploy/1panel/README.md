# 1Panel Docker 部署

这个目录只部署 Web 版，不包含 `desktop/` 或 `desktop-app/`。

## 1Panel 使用方式

1. 在服务器创建目录，例如 `/opt/1panel/apps/xiaobaitu-web/xiaobaitu-web/`。
2. 上传仓库中的 Web 部署文件到该目录，至少包含：
   - `app.py`
   - `Dockerfile.web`
   - `requirements-web.txt`
   - `deploy/1panel/docker-compose.yml`
   - `deploy/1panel/.env.example`
3. 在 `deploy/1panel/` 下复制环境文件：

   ```bash
   cp .env.example .env
   ```

4. 在 `.env` 中填写 `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`，并按需修改 `APP_PORT`。
5. 在 1Panel 的“容器 / Compose”中选择 `deploy/1panel/docker-compose.yml` 创建应用。

如果你用 1Panel 的网站反向代理：

- 代理目标填 `http://127.0.0.1:8501`
- 开启 WebSocket
- 域名启用 HTTPS 后再公开访问

默认访问：

- `http://服务器IP:8501`
- 健康检查：`http://服务器IP:8501/_stcore/health`

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
