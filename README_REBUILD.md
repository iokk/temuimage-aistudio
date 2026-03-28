# Next.js + FastAPI Rebuild V1

这是新系统的 V1 原型，可直接进入部署和联调阶段。

## 目录

- `apps/web`: Next.js 15 前端
- `apps/api`: FastAPI API
- `apps/worker`: Celery worker
- `packages/db`: Prisma schema
- `packages/shared`: 共享类型占位

## 当前 V1 已完成

- Casdoor 登录骨架与模式分流
- 四个核心能力页：`批量出图`、`快速出图`、`标题优化`、`图片翻译`
- 统一任务中心、任务详情、状态时间线
- 管理后台运行诊断
- 个人设置 / 团队设置面板
- 任务存储后端与执行后端状态可见
- Prisma 初始迁移 + system 用户 bootstrap
- Docker 与 `docker-compose.rebuild.yml` 启动链

## 本地启动顺序

1. 准备环境变量，参考 `.env.rebuild.example`
2. 启动基础设施：`docker compose -f docker-compose.rebuild.yml up -d postgres redis`
3. 初始化数据库：`pnpm deploy:db`
4. 启动 API / Worker / Web：`docker compose -f docker-compose.rebuild.yml up --build`

## 生产建议

- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- PostgreSQL 与 Redis 必须同时可用
- 先执行 `pnpm deploy:db`，再启动 API / Worker / Web
- 若系统回退到 `memory` 或 `inline`，请先查看管理后台和团队设置里的运行警告
- 发布前逐项核对 `docs/rebuild-v1-release-checklist.md`
- 部署执行步骤参考 `docs/rebuild-v1-deploy-runbook.md`
- Zeabur 专项部署参考 `docs/zeabur-rebuild-v1.md`

## 当前限制

- 业务能力仍为预览/原型链路，尚未接入真实图像生成供应商执行
- 团队权限目前仍主要依赖环境变量，数据库化成员权限还未完全接通
