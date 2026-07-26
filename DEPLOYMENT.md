# 部署说明

## 当前部署定位

这个仓库现在只服务于：

1. 个人本地 `desktop/mac`
2. `self-hosted` 单机服务器版

不再包含原来的多服务 `rebuild` 发布路径。

## 推荐部署

推荐使用 Docker Compose 在 Linux 单机上部署。

```bash
git clone https://github.com/iokk/xiaobaitu.git
cd xiaobaitu
cp .env.example .env
./deploy.sh install
```

## 1Panel 部署

推荐在 1Panel 中使用仓库根目录的 `docker-compose.yml`，或使用
`deploy/1panel/docker-compose.yml` 作为专用 Compose 文件。

服务器目录建议：

```bash
/opt/1panel/apps/xiaobaitu-web/xiaobaitu-web
```

1Panel 创建 Compose 应用时：

- Compose 文件：`docker-compose.yml`
- 环境文件：`.env`
- 对外端口：默认 `8501`
- 数据目录：`./data` 会挂载到容器 `/app/data`

如果服务器只用于 Web 版，不需要上传或构建 `desktop/`、`desktop-app/`。
当前 Docker 构建已经只复制 `app.py` 与 Web 依赖。

## 关键环境变量

- `APP_RUNTIME=server`
- `APP_PORT=8501`
- `ECOMMERCE_WORKBENCH_DATA_DIR=/app/data`
- `ECOMMERCE_WORKBENCH_PROJECTS_DIR=/app/data/projects`
- `FILE_STORAGE_PATH=/app/data/files`
- `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`
- `XIAOBAITU_DEMO_MODE=0`，生产建议保持关闭；临时演示可设为 `1`

## 防火墙与反向代理

直接 IP 访问时，放行 TCP `8501`：

```bash
ufw allow 8501/tcp
```

如果使用 1Panel 网站反向代理，建议：

- 站点 upstream 指向 `http://127.0.0.1:8501`
- 开启 WebSocket 支持
- 开启 HTTPS 后再对外展示

## 服务器版行为边界

- 用户通过浏览器上传文件
- 生成结果先保存在服务器项目中心
- 用户从项目中心下载 ZIP 或图片
- 不提供“打开本地文件夹”
- 不提供“选择访问者本地保存目录”

## 首次启动检查

1. 打开 [http://localhost:8501](http://localhost:8501)
2. 访问 `⚙️ 提供商设置`
3. 检查默认 provider 是否已创建
4. 运行一次标题生成
5. 运行一次图片翻译
6. 到 `📚 项目中心` 确认结果已进入服务器项目中心
