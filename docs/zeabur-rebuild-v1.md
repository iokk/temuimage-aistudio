# Zeabur Rebuild V1 Deployment Guide

## Service layout

- `web` → `apps/web/Dockerfile`
- `api` → `apps/api/Dockerfile`
- `worker` → `apps/worker/Dockerfile`
- `postgres` → Zeabur PostgreSQL
- `redis` → Zeabur Redis

## Environment source

- Use `.env.zeabur.production.example`
- Control-panel copy template: `docs/zeabur-console-fill-template.md`
- Web and API/Worker share Casdoor and team access envs
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
- `API_APP_NAME`
- `API_APP_VERSION`
- `SYSTEM_ENCRYPTION_KEY`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`

## Deploy sequence on Zeabur

1. Create PostgreSQL service
2. Create Redis service
3. Create `api` service from `apps/api/Dockerfile`
4. Create `worker` service from `apps/worker/Dockerfile`
5. Create `web` service from `apps/web/Dockerfile`
6. Fill env vars from `.env.zeabur.production.example`
7. Run `pnpm deploy:db` from a trusted CI/local machine with production `DATABASE_URL`
8. Restart `api` and `worker`

## Release verification

Use:

```bash
API_BASE_URL=https://api.example.com WEB_BASE_URL=https://web.example.com ./scripts/zeabur_rebuild_release.sh
```

You can first generate a fill-ready secret template with:

```bash
python3 scripts/generate_zeabur_env.py --web-domain studio.example.com --api-domain api.example.com
```

## Success criteria

- `/admin` shows `Readiness = ready`
- `active_backend = database`
- `active_execution_backend = celery`
- No blocking warnings remain
