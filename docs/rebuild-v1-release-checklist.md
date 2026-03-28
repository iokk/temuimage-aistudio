# Rebuild V1 Release Checklist

## Environment

- Set `DATABASE_URL`
- Set `REDIS_URL`
- Set `JOB_STORE_BACKEND=database`
- Set `ASYNC_JOB_BACKEND=celery`
- Set `NEXTAUTH_URL`
- Set `NEXTAUTH_SECRET`
- Set `CASDOOR_ISSUER`
- Set `CASDOOR_CLIENT_ID`
- Set `CASDOOR_CLIENT_SECRET`
- Set `TEAM_ADMIN_EMAILS`
- Set `TEAM_ALLOWED_EMAIL_DOMAINS`

## Database

- Run `pnpm prisma:validate`
- Run `pnpm deploy:db`
- Confirm `system@xiaobaitu.local` is seeded

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

## Go-live gate

- No blocking warnings in admin runtime panel
- `ready_for_distributed_workers=true`
- `active_backend=database`
- `active_execution_backend=celery`
