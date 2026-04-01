# Next.js + FastAPI Rebuild v1

这是当前正式发布线的实现目录说明，面向 `rebuild-v1.0.0`。

## 目录

- `apps/web`: Next.js 15 前端
- `apps/api`: FastAPI API
- `apps/worker`: Celery worker
- `packages/db`: Prisma schema
- `packages/shared`: 共享类型占位

## 当前状态

- Casdoor 单一正式登录入口
- 四个核心能力页：`批量出图`、`快速出图`、`标题优化`、`图片翻译`
- 统一任务中心、任务详情、状态时间线
- 管理后台运行诊断
- 个人设置 / 团队设置面板
- 任务存储后端与执行后端状态可见
- Prisma 初始迁移 + system 用户 seed
- Docker 与 `docker-compose.rebuild.yml` 启动链

## 本地启动顺序

1. 准备环境变量，参考 `.env.rebuild.example`
2. 启动基础设施：`docker compose -f docker-compose.rebuild.yml up -d postgres redis`
3. 启动 API / Worker / Web：`docker compose -f docker-compose.rebuild.yml up --build`
4. 通过 Casdoor 登录

## 生产建议

- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- PostgreSQL 与 Redis 必须同时可用
- Casdoor 为正式统一身份入口
- `pnpm deploy:db` 仅用于后续 Prisma migration 升级
- 若系统回退到 `memory` 或 `inline`，先查看管理后台运行警告
- 发布前逐项核对 `docs/rebuild-v1-release-checklist.md`
- 部署执行步骤参考 `docs/rebuild-v1-deploy-runbook.md`
- Zeabur 专项部署参考 `docs/zeabur-rebuild-v1.md`
- Zeabur 自动化部署入口参考：`docs/zeabur-auto-deploy.md`
- Zeabur 控制台逐项填写模板：`docs/zeabur-console-fill-template.md`

## 当前限制

- 业务能力仍为预览/原型链路，尚未接入真实图像生成供应商执行
- 团队权限仍主要依赖环境变量，数据库化成员权限还未完全接通
