# TuLite 部署说明

## 部署定位

本仓库服务于两种形态：

1. 个人本地 `desktop/mac`（直接 `streamlit run app.py`）
2. `self-hosted` 单机服务器版（Docker Compose）

架构为单进程单实例设计（本地 JSON 文件 + 进程内任务队列），**不支持多副本/水平扩展**。个人与小团队使用足够。

## 推荐部署（Docker Compose）

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
cp .env.example .env   # 按需修改
docker compose up -d
```

或使用脚本：

```bash
./deploy.sh install
```

访问 http://服务器IP:8501

## 1Panel 部署

使用仓库根目录的 `docker-compose.yml`，或 `deploy/1panel/docker-compose.yml` 作为专用 Compose 文件。

服务器目录建议：

```bash
/opt/1panel/apps/tulite/tulite
```

1Panel 创建 Compose 应用时：

- Compose 文件：`docker-compose.yml`
- 环境文件：`.env`
- 对外端口：默认 `8501`
- 数据目录：`./data` 挂载到容器 `/app/data`

服务器只跑 Web 版时无需上传 `desktop/`、`desktop-app/`（Docker 构建只复制 `app.py` 与 Web 依赖）。

## 关键环境变量

- `APP_RUNTIME=server`
- `APP_PORT=8501`
- `ECOMMERCE_WORKBENCH_DATA_DIR=/app/data`
- `ECOMMERCE_WORKBENCH_PROJECTS_DIR=/app/data/projects`
- `FILE_STORAGE_PATH=/app/data/files`
- `FILE_RETENTION_DAYS=7`（过期文件保留天数，到期每小时自动清理）
- `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`（可选，首次启动自动创建默认提供商）
- `XIAOBAITU_DEMO_MODE=0`（生产必须保持关闭）

## 安全与数据

- **API Key 存储**：服务器环境自动使用本地密钥加密存储（Fernet），密钥文件为 `data/.secret_key`（权限 600）。请将 `data/` 目录纳入备份，但**不要**提交进仓库。
- **日志**：`data/logs/app.log`，滚动 5MB × 3 份，任务失败会记录完整堆栈，排查问题优先看这里。
- **任务隔离**：任务记录按浏览器会话隔离展示，任务执行并发上限全局共享（默认 2，代码中 `MAX_ACTIVE_TASKS`）。

## 防火墙与反向代理

直接 IP 访问时放行 TCP `8501`：

```bash
ufw allow 8501/tcp
```

使用 1Panel/Nginx 反向代理时：

- upstream 指向 `http://127.0.0.1:8501`
- 必须开启 WebSocket 支持（Streamlit 依赖）
- 建议开启 HTTPS 后再对外访问

## 服务器版行为边界

- 用户通过浏览器上传文件；生成结果先保存在服务器项目中心，从项目中心下载 ZIP 或图片
- 不提供"打开本地文件夹"、"选择访问者本地保存目录"

## 首次启动检查

1. 打开 http://localhost:8501
2. 进入 `⚙️ 提供商设置`，确认默认 provider 已创建、测试连接通过
3. 运行一次标题生成、一次图片翻译
4. 到 `📚 项目中心` 确认结果已归档
5. 确认 `data/logs/app.log` 已生成

## 升级

```bash
cd tulite
git pull
docker compose up -d --build
```

`data/` 目录内的配置、任务与文件在升级时会保留。
