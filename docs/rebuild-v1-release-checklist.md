# Rebuild v1 Release Checklist

## Release metadata

- Confirm release tag is `rebuild-v1.0.0`
- Confirm API version is `1.0.0`
- Confirm rebuild docs are the primary docs
- Confirm legacy Streamlit docs are treated as archive/history only

## Environment

- Set `DATABASE_URL`
- Set `REDIS_URL`
- Set `JOB_STORE_BACKEND=database`
- Set `ASYNC_JOB_BACKEND=celery`
- Set `AUTO_BOOTSTRAP_DB=true` on API and `false` on worker
- Set `NEXTAUTH_URL`
- Set `NEXTAUTH_SECRET`
- Set `CASDOOR_ISSUER`
- Set `CASDOOR_CLIENT_ID`
- Set `CASDOOR_CLIENT_SECRET`
- Set `CASDOOR_API_AUDIENCE` if required
- Set `TEAM_ADMIN_EMAILS`
- Set `TEAM_ALLOWED_EMAIL_DOMAINS`
- Set `SYSTEM_ENCRYPTION_KEY`

## Database

- Run `pnpm prisma:validate`
- Let API first startup create missing tables and seed `system@xiaobaitu.local`
- Run `pnpm deploy:db` only when shipping Prisma schema changes beyond first bootstrap

## Services

- Start PostgreSQL
- Start Redis
- Start API
- Start Worker
- Start Web

## Smoke checks

- Open `/login`
- Confirm Casdoor login loads
- Open `/admin`
- Confirm runtime panel shows `ready` or expected warnings
- Open `/tasks`
- Confirm task center loads
- Run one task from `/title`
- Confirm task reaches `completed`
- Open `/tasks/[jobId]`
- Confirm timeline and structured result render

## Default models

- Confirm title default is `gemini-3.1-pro`
- Confirm translate analysis default is `gemini-3.1-pro`
- Confirm translate image default is `gemini-3.1-flash-image-preview`
- Confirm quick image default is `gemini-3.1-flash-image-preview`
- Confirm batch image default is `gemini-3.1-flash-image-preview`

## Go-live gate

- No blocking warnings in admin runtime panel
- `ready_for_distributed_workers=true`
- `active_backend=database`
- `active_execution_backend=celery`
- `auth_provider=Casdoor`
