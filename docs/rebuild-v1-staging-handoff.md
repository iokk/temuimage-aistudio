# Rebuild v1 Staging Handoff

## Target

Use this checklist before the formal `rebuild-v1.0.0` production cutover.

## Services

- `web`
- `api`
- `worker`
- `postgresql`
- `redis`

## Required staging env

- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `NEXT_PUBLIC_API_BASE_URL`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`
- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`

## Before validation

1. Confirm at least one staging admin email is present in `TEAM_ADMIN_EMAILS`
2. Obtain a short-lived Casdoor access token for that admin
3. Export it as `API_BEARER_TOKEN`

## Validation commands

```bash
pnpm build:web
pnpm prisma:validate
python3 -m py_compile apps/api/core/auth.py apps/api/job_repository.py apps/api/routers/jobs.py apps/api/routers/system.py apps/api/routers/title.py apps/api/routers/quick.py apps/api/routers/batch.py apps/api/routers/translate.py apps/api/task_processor.py apps/api/bootstrap_db.py apps/api/db/models.py apps/api/core/config.py
```

```bash
API_BASE_URL=https://staging-api.example.com WEB_BASE_URL=https://staging-web.example.com API_BEARER_TOKEN=<casdoor-admin-token> ./scripts/zeabur_rebuild_release.sh
```

## Manual checks

1. Sign in through Casdoor
2. Open `/admin`
3. Confirm `auth_provider = Casdoor`
4. Confirm `active_backend = database`
5. Confirm `active_execution_backend = celery`
6. Confirm all default models are `gemini-3.1-*`
7. Submit one task from `/title`, `/quick`, `/batch`, and `/translate`
8. Confirm `/tasks` and `/tasks/[jobId]` are owner-scoped and working

## Exit criteria

- `Readiness = ready`
- No blocking warnings
- Casdoor login succeeds
- Admin pages load normally
- Task ownership and polling behave correctly
