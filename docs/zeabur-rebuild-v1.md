# Zeabur Rebuild v1 Deployment Guide

## Service layout

- `web` -> `apps/web/Dockerfile`
- `api` -> `apps/api/Dockerfile`
- `worker` -> `apps/worker/Dockerfile`
- `postgresql` -> Zeabur PostgreSQL
- `redis` -> Zeabur Redis

This five-service layout is the official production shape for `rebuild-v1.0.0`.

## Environment source

- Use `.env.zeabur.production.example`
- Control-panel copy template: `docs/zeabur-console-fill-template.md`
- Web, API, and Worker share Casdoor and team access envs
- API and Worker must share the same `DATABASE_URL` and `REDIS_URL`

## Required values

### Web

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`

### API / Worker

- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `AUTO_BOOTSTRAP_DB=true` on API for first-start table creation and `system` seed
- `AUTO_BOOTSTRAP_DB=false` on worker
- `API_APP_NAME`
- `API_APP_VERSION=1.0.0`
- `SYSTEM_ENCRYPTION_KEY`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `CASDOOR_API_AUDIENCE` if your token audience is customized

## Deploy sequence on Zeabur

For the canonical template publishing / Deploy Button flow, see `docs/zeabur-auto-deploy.md`.

1. Create PostgreSQL service
2. Create Redis service
3. Create `api` service from `apps/api/Dockerfile`
4. Create `worker` service from `apps/worker/Dockerfile`
5. Create `web` service from `apps/web/Dockerfile`
6. Fill env vars from `.env.zeabur.production.example`
7. Confirm `api` has `AUTO_BOOTSTRAP_DB=true` and `worker` has `AUTO_BOOTSTRAP_DB=false`
8. Wait for `api` startup to create tables and seed `system@xiaobaitu.local`
9. Sign in through Casdoor and verify `/admin`
10. Run `pnpm deploy:db` later only when a release adds Prisma migrations that `create_all()` cannot apply

## Release verification

```bash
API_BASE_URL=https://api.example.com WEB_BASE_URL=https://web.example.com API_BEARER_TOKEN=<casdoor-admin-token> ./scripts/zeabur_rebuild_release.sh
```

`API_BEARER_TOKEN` should be a short-lived Casdoor access token for an admin email listed in `TEAM_ADMIN_EMAILS`.

You can generate a fill-ready template with:

```bash
python3 scripts/generate_zeabur_env.py --web-domain studio.example.com --api-domain api.example.com --casdoor-issuer https://casdoor.example.com --admin-emails owner@example.com --allowed-domains example.com
```

## Success criteria

For the final online acceptance gate, use `docs/rebuild-v1-release-checklist.md` as the canonical checklist.

- `/admin` shows `Readiness = ready`
- `active_backend = database`
- `active_execution_backend = celery`
- `auth_provider = Casdoor`
- No blocking warnings remain
- `system@xiaobaitu.local` exists without a manual seed step on first deploy
