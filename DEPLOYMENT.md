# TuLite 部署说明

## 部署定位

本仓库服务于两种形态：

1. 个人本地 `desktop/mac`（运行 `python3 run_tulite.py`）
2. `self-hosted` 单机服务器版（Docker Compose）

任务状态保存在 SQLite，配置与项目索引保存在本地 JSON。Streamlit 页面只提交、查询和取消任务，独立 `TaskEngine` 主管后台领取与执行；多标签页共享任务中心，排队任务可跨重启恢复。当前部署仍推荐单应用实例，未来独立 worker 可复用同一引擎和执行器注册表。

## 推荐部署（Docker Compose）

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
cp .env.example .env
# 必须先在 .env 中设置你自己的高强度随机 APP_ACCESS_PASSWORD
docker compose up -d
```

或使用脚本：

```bash
./deploy.sh install
```

默认仅监听 `127.0.0.1:8501`，供服务器本机或本机反向代理访问。
如需直接通过服务器 IP 访问，必须先设置高强度访问口令，再将
`APP_BIND_ADDRESS` 显式改为 `0.0.0.0`。

## 1Panel 部署

使用仓库根目录的 `docker-compose.yml`，或 `deploy/1panel/docker-compose.yml` 作为专用 Compose 文件。

服务器目录建议：

```bash
/opt/1panel/apps/tulite/tulite
```

1Panel 创建 Compose 应用时：

- Compose 文件：`docker-compose.yml`
- 环境文件：`.env`
- 宿主监听：默认 `127.0.0.1:8501`
- 数据目录：`./data` 挂载到容器 `/app/data`

服务器只跑 Web 版时无需上传 `desktop/`、`desktop-app/`（Docker 构建会复制 `app.py`、`task_engine.py`、`task_store.py`、`run_tulite.py` 与 Web 依赖）。

## 关键环境变量

- `APP_RUNTIME=server`
- `APP_BIND_ADDRESS=127.0.0.1`（安全默认；仅本机和本机反向代理可访问）
- `APP_PORT=8501`
- `APP_ACCESS_PASSWORD`（服务器模式必填；缺失时 Compose 拒绝启动，应用也会停止访问）
- `ECOMMERCE_WORKBENCH_DATA_DIR=/app/data`
- `ECOMMERCE_WORKBENCH_PROJECTS_DIR=/app/data/projects`
- `FILE_STORAGE_PATH=/app/data/files`
- `FILE_RETENTION_DAYS=7`（过期文件保留天数，到期每小时自动清理）
- `TULITE_RUNNER_ID`（可选；runner 名称前缀，实际进程身份会自动追加 PID 与启动 UUID）
- `TASK_RUNNER_LEASE_SECONDS=30`（worker 租约；进程失联后才允许将运行中任务标记为中断）
- `TASK_SUPERVISOR_INTERVAL_SECONDS=5`（后台调度检查间隔，不触发页面刷新）
- `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`（可选，首次启动自动创建默认提供商）
- `XIAOBAITU_DEMO_MODE=0`（生产必须保持关闭）

## 安全与数据

- **API Key 存储**：在提供商设置中录入的 Key 使用 Fernet 加密后写入提供商配置，密钥文件为 `data/.secret_key`（权限 600）。通过 `GOOGLE_API_KEY` / `GEMINI_API_KEY` 注入的 Key 始终由容器环境或 `.env` 管理，不会复制到 `providers.json`；`.env` 本身仍含敏感明文，应设置权限 600。请将 `data/` 目录纳入备份，但**不要**提交 `data/` 或 `.env`。
- **访问控制**：服务器模式必须配置 `APP_ACCESS_PASSWORD`。Compose 默认只绑定宿主回环地址；对外发布应通过启用 HTTPS/WebSocket 的反向代理，或在明确需要直接 IP 访问时显式设置 `APP_BIND_ADDRESS=0.0.0.0`。
- **日志**：`data/logs/app.log`，滚动 5MB × 3 份，任务失败会记录完整堆栈，排查问题优先看这里。
- **任务持久化**：`data/tasks.sqlite3` 是任务状态真相源；同一安装实例的标签页共享任务，并发上限全局共享（默认 2）。数据库启动时按版本事务迁移，v2 已包含优先级与延迟领取索引。请将 SQLite 主文件及其 WAL/SHM 文件与整个 `data/` 目录一并备份。
- **重启策略**：排队任务保留并继续调度；重启前未确认完成的运行中任务标记为中断，不自动重放图片请求。

## 防火墙与反向代理

推荐让 1Panel/Nginx 反向代理到 `http://127.0.0.1:8501`，并开启
HTTPS 与 WebSocket 支持。只有明确选择直接 IP 访问、已设置高强度
`APP_ACCESS_PASSWORD` 且已将 `APP_BIND_ADDRESS=0.0.0.0` 时，才放行
TCP `8501`：

```bash
ufw allow 8501/tcp
```

- upstream 指向 `http://127.0.0.1:8501`
- 必须开启 WebSocket 支持（Streamlit 依赖）
- 必须开启 HTTPS 后再对外访问

## 服务器版行为边界

- 用户通过浏览器上传文件；生成结果先保存在服务器项目中心，从项目中心下载 ZIP 或图片
- 不提供"打开本地文件夹"、"选择访问者本地保存目录"

## 首次启动检查

1. 打开 http://localhost:8501
2. 进入 `⚙️ 提供商设置`，确认默认 provider 已创建、测试连接通过
3. 在服务容器内运行以下命令，确认模型、文本与 Responses 检查通过；该命令不会输出 API Key

   ```bash
   docker compose exec workbench python scripts/verify_provider.py
   ```

4. 需要验收真实出图时，在服务容器内显式运行以下命令；这会产生一次上游图片费用

   ```bash
   docker compose exec workbench python scripts/verify_provider.py \
     --live-image \
     --image-output /app/data/provider-acceptance.png
   ```
5. 运行一次标题生成、一次图片翻译
6. 到 `📚 项目中心` 确认结果已归档
7. 确认 `data/logs/app.log` 已生成

## 升级

```bash
cd tulite
git pull
docker compose up -d --build
```

`data/` 目录内的配置、任务与文件在升级时会保留。

升级前建议先完整备份 `data/`，升级后执行：

```bash
docker compose config --quiet
docker compose ps
curl --fail http://127.0.0.1:8501/_stcore/health
```

如需回滚，切换到 `CHANGELOG.md` 中最近的已验收标签，恢复升级前的整个 `data/` 备份并重新构建。不要只复制 `tasks.sqlite3`，SQLite 的 WAL/SHM 文件和项目文件必须保持同一备份时点。
