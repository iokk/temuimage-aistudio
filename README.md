# 电商出图工作台

个人 self-hosted 主线版本，面向两种运行形态：

1. `desktop/mac`
2. `server/web`

两种模式共用同一套模板库、任务队列、项目中心、提供商配置和核心生成流程，但文件能力按运行环境分流：

- `desktop/mac` 可以打开本地文件、打开本地文件夹、选择本地保存目录
- `server/web` 只走浏览器上传和下载，结果先保存在服务器项目中心，不直接操作访问者电脑文件系统

## 当前主线

仓库当前只保留个人部署版主线：

- `app.py`：Streamlit 主应用
- `desktop/`：Mac 本地桌面壳辅助代码
- `desktop-app/`：桌面端实验壳
- `docs/superpowers/`：设计、维护规范和演进文档

旧的 `rebuild` 多服务架构已经从主工作树移除，不再作为正式部署路径。

## 运行模式

通过环境变量切换：

```bash
APP_RUNTIME=desktop
APP_RUNTIME=server
```

默认规则：

- 本地直接运行时默认 `desktop`
- Docker / Linux 服务器部署时默认 `server`

## 功能结构

- `🚀 智能组图`
- `🎨 快速出图 / 图片翻译`
- `🏷️ 标题生成`
- `📚 项目中心`
- `🧩 模板库`
- `⚙️ 提供商设置`
- `🛠️ 系统设置`

## Linux self-hosted 快速部署

```bash
git clone https://github.com/iokk/xiaobaitu.git
cd xiaobaitu
cp .env.example .env
./deploy.sh install
```

默认访问地址：

- [http://localhost:8501](http://localhost:8501)

## 本地开发启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

如果你要强制本地以桌面模式运行：

```bash
APP_RUNTIME=desktop streamlit run app.py
```

如果你要在本机模拟服务器模式：

```bash
APP_RUNTIME=server streamlit run app.py
```

## 数据目录

默认数据目录：

- 本地开发：`./data`
- Docker / 服务器：`/app/data`

重要文件：

- `data/providers.json`
- `data/settings.json`
- `data/templates.json`
- `data/title_templates.json`
- `data/tasks.json`
- `data/history.json`

项目结果默认目录：

- `desktop/mac`：`~/Downloads/电商出图工作台`
- `server/web`：`/app/data/projects`

## 提供商与密钥

- 如果 `.env` 中提供了 `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`，并且本地没有 provider 配置，应用会自动创建默认 Gemini 提供商
- `desktop/mac` 优先使用 macOS Keychain 保存 provider 密钥
- `server/web` 不依赖 Keychain，provider 密钥按服务器运行方式保存

## 服务器模式的文件规则

这是这版最重要的边界：

- 用户通过浏览器上传素材
- 生成结果先落到服务器项目中心
- 用户从项目中心下载 ZIP 或结果文件
- 服务器版不显示“打开本地文件夹”
- 服务器版不允许把访问者电脑路径当作保存目录

## 文档

- [部署说明](/tmp/xiaobaitu/DEPLOYMENT.md)
- [系统细节设计](/tmp/xiaobaitu/docs/superpowers/specs/2026-04-21-system-detail-design.md)
- [模板管理设计](/tmp/xiaobaitu/docs/superpowers/specs/2026-04-21-template-management-design.md)
- [双运行模式设计](/tmp/xiaobaitu/docs/superpowers/specs/2026-04-23-self-hosted-runtime-design.md)

