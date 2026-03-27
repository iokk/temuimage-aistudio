# Next.js + FastAPI 一次性替换重构设计

## Goal

用 `Next.js 15 + FastAPI + Celery + Redis + PostgreSQL + Prisma + Casdoor` 重构当前产品，并最终一次性替换现有 Streamlit 版本。

## Core Decisions

- 前端：`Next.js 15 + App Router + TypeScript + Tailwind + shadcn/ui`
- 后端：`FastAPI`
- 队列：`Celery + Redis`
- 数据库：`PostgreSQL`
- 认证：`Casdoor`
- ORM/迁移：`Prisma` 为核心 schema source of truth，FastAPI 只映射表结构，不主导迁移
- 文件存储：先本地文件系统，后续再切对象存储

## Product Modes

- `个人模式`
  - 使用自己的 Gemini / Relay 凭据
- `团队模式`
  - Casdoor 登录
  - 团队管理员统一维护系统配置
- `游客模式` 不开放

## App Structure

- `/` 工作台
- `/batch`
- `/quick`
- `/title`
- `/translate`
- `/tasks`
- `/settings/personal`
- `/settings/team`
- `/admin`

## Migration Strategy

- 空库起步
- 不迁旧数据
- 旧 Streamlit 版本保留为历史参考和回滚点
- 新系统稳定后一次性切换上线

## Zeabur Deployment

推荐多服务模板：

- `web`
- `api`
- `worker`
- `postgres`
- `redis`

## Scope of Phase 1

本阶段只做新系统骨架：

- monorepo 目录
- Next.js 基础壳层
- FastAPI 基础应用
- Celery worker 基础入口
- Prisma schema 初版
- Zeabur 模板方向更新

不在本阶段迁移具体业务页面逻辑。
