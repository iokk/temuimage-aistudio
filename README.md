# TuLite · 图 Lite

轻量级跨境电商 AI 出图工作台。单文件 Streamlit 应用，支持 Gemini / OpenAI（GPT Image）协议出图、批量组图、多语言产品标题生成，可本地跑，也可一键 Docker 私有部署。

## 功能

- **🚀 智能组图**：上传产品图 → AI 分析商品 → 按模板批量生成主图/场景图/细节图
- **🎨 快速出图 / 图片翻译**：单张图快速生成、图内文字翻译改写
- **🏷️ 标题生成**：基于产品图的多语言标题生成（支持 15 种跨境主流语言），可在 GPT / Gemini / Grok 常见视觉模型间选择
- **📚 项目中心**：任务记录、生成结果按项目归档，支持回收站与自动过期清理
- **🧩 模板库 / 提示词管理**：出图模板与语言规则均可在页面内直接编辑
- **⚙️ 多提供商**：支持 `gemini`（官方/兼容中转）、`relay`（Gemini 协议中转）、`openai`（标准 OpenAI 协议，含 GPT Image 文生图与图生图）三种接入类型

## 技术特点

- 单文件 `app.py`，依赖极少，启动快，方便自部署和二次修改
- 任务队列内建并发上限（默认同时 2 个任务），带 429/5xx 指数退避重试
- 多会话使用时任务记录按浏览器会话隔离展示
- API Key 存储：macOS 桌面版走系统 Keychain；服务器/容器部署自动降级为本地密钥加密存储（Fernet），不明文落盘
- 文件日志（`data/logs/app.log`，滚动 5MB×3），任务失败自动记录完整堆栈
- 过期文件每小时自动清理

## 快速开始（本地）

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
pip install -r requirements.txt
streamlit run app.py
```

打开 http://localhost:8501 ，在「⚙️ 提供商设置」里填入你的 API Key 即可使用。

## 运行模式

通过环境变量 `APP_RUNTIME` 切换：

- `desktop`（本地直接运行时默认）：可打开本地文件夹、自选保存目录
- `server`（Docker/Linux 部署时默认）：只走浏览器上传下载，结果保存在服务器项目中心

## 部署

推荐 Docker Compose 单机部署，详见 [DEPLOYMENT.md](DEPLOYMENT.md)：

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
cp .env.example .env   # 按需修改
docker compose up -d
```

## 目录结构

```
app.py              # 主应用（单文件）
requirements.txt    # 完整依赖
requirements-web.txt# 仅 Web 部署的精简依赖
Dockerfile / Dockerfile.web / docker-compose.yml
deploy/1panel/      # 1Panel 面板部署专用文件
desktop/ desktop-app/  # macOS 桌面壳（仅本地桌面版需要）
data/               # 运行时数据（配置/任务/文件/日志），已 gitignore
```

## 注意事项

- 当前架构为**单进程单实例**设计（本地 JSON 文件存储状态），不支持多副本/水平扩展；个人和小团队使用完全够用
- 生产部署请勿开启 `XIAOBAITU_DEMO_MODE`
- API Key 属于敏感信息，`.env` 与 `data/` 目录不要提交到仓库

## License

私有项目，仅供个人/团队内部使用。
