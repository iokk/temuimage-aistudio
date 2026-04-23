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

## 关键环境变量

- `APP_RUNTIME=server`
- `APP_PORT=8501`
- `ECOMMERCE_WORKBENCH_DATA_DIR=/app/data`
- `ECOMMERCE_WORKBENCH_PROJECTS_DIR=/app/data/projects`
- `FILE_STORAGE_PATH=/app/data/files`
- `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`

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

