# TuLite · 图 Lite

轻量级跨境电商 AI 出图工作台。基于 Streamlit，支持 Gemini / OpenAI（GPT Image）协议出图、批量组图、多语言产品标题生成，可本地跑，也可一键 Docker 私有部署。

## 功能

- **🚀 智能组图**：上传产品图 → AI 分析商品 → 按模板批量生成主图/场景图/细节图
- **🎨 快速出图 / 图片翻译**：单张图快速生成、图内文字翻译改写
- **🏷️ 标题生成**：基于产品图的多语言标题生成（支持 15 种跨境主流语言），可在 GPT / Gemini / Grok 常见视觉模型间选择
- **📚 项目中心**：任务记录、生成结果按项目归档，支持回收站与自动过期清理
- **🧩 模板库 / 提示词管理**：出图模板与语言规则均可在页面内直接编辑
- **⚙️ 多提供商**：支持 `gemini`（官方/兼容中转）、`relay`（Gemini 协议中转）、`openai`（标准 OpenAI 协议，含 GPT Image 文生图与图生图）三种接入类型

## 技术特点

- Streamlit 页面只负责提交、查询和取消；`TaskEngine` 独立负责后台领取、心跳、执行和终态提交
- 任务队列使用 SQLite 事务持久化，内建并发上限（默认同时 2 个任务）、优先级与延迟执行字段
- 同一安装实例的多个标签页共享任务中心；排队任务可跨热更新与进程重启保留
- 重启前正在执行的图片任务会标记为中断，不自动重放，避免重复生成与重复计费
- API Key 存储：在提供商设置中录入的 Key，macOS 桌面版写入系统 Keychain，服务器/容器使用 Fernet 加密后写入提供商配置。通过 `GOOGLE_API_KEY` / `GEMINI_API_KEY` 注入的 Key 由运行环境或 `.env` 管理，不会复制到 `providers.json`；`.env` 本身仍含敏感明文，必须限制权限且不得提交
- 文件日志（`data/logs/app.log`，滚动 5MB×3），任务失败自动记录完整堆栈
- 过期文件每小时自动清理

## 快速开始（本地）

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
pip install -r requirements.txt
python3 run_tulite.py
```

打开 http://localhost:8501 ，在「⚙️ 提供商设置」里填入你的 API Key 即可使用。

### 提供商验收

使用已保存的当前提供商检查密钥可用性、模型目录、文本接口与 Responses 接口。命令只输出脱敏 JSON，不接受也不打印 API Key：

```bash
python3 scripts/verify_provider.py
```

真实图片能力需要单独显式开启，并会产生一次上游图片费用。输出路径应放在已忽略的 `data/` 或仓库外：

```bash
python3 scripts/verify_provider.py \
  --live-image \
  --image-output data/provider-acceptance.png
```

## 运行模式

通过环境变量 `APP_RUNTIME` 切换：

- `desktop`（本地直接运行时默认）：可打开本地文件夹、自选保存目录
- `server`（Docker/Linux 部署时默认）：只走浏览器上传下载，结果保存在服务器项目中心

## 部署

推荐 Docker Compose 单机部署，详见 [DEPLOYMENT.md](DEPLOYMENT.md)：

```bash
git clone https://cnb.cool/imqie/tulite.git
cd tulite
cp .env.example .env
# 必须先在 .env 中设置你自己的高强度随机 APP_ACCESS_PASSWORD
docker compose up -d
```

## 目录结构

```
app.py              # Streamlit 主应用
task_engine.py      # 后台主管、执行器注册表、检查点与统一结果契约
task_store.py       # SQLite 任务仓库、状态机与原子任务认领
task_status.py      # 任务生命周期词汇与合法状态迁移
run_tulite.py       # 服务入口（先启动后台任务监督器，再启动 Streamlit）
provider_acceptance.py / scripts/verify_provider.py  # 脱敏提供商验收
requirements.txt    # 完整依赖
requirements-web.txt# 仅 Web 部署的精简依赖
Dockerfile / Dockerfile.web / docker-compose.yml
deploy/1panel/      # 1Panel 面板部署专用文件
desktop/ desktop-app/  # macOS 桌面壳（仅本地桌面版需要）
data/               # 运行时数据（配置/任务/文件/日志），已 gitignore
```

## 注意事项

- 当前部署仍推荐**单应用实例**运行；任务领取已支持 SQLite 原子事务、进程唯一 runner 与租约，后续可沿 `TaskHandler` 注册表拆出独立 worker
- 生产部署请勿开启 `XIAOBAITU_DEMO_MODE`
- API Key 属于敏感信息，`.env` 与 `data/` 目录不要提交到仓库

## License

私有项目，仅供个人/团队内部使用。
