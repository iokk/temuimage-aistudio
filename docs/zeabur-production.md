# Zeabur Production Plan For Rebuild V1

## Target topology

- `web` on Zeabur
- `api` on Zeabur
- `worker` on Zeabur
- managed PostgreSQL
- managed Redis

Repository-shipped `template.yaml` is now the recommended deployment entrypoint.

The services should remain stateless. Persistent business state must live in PostgreSQL and Redis.

## Required env vars

- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`
- `SYSTEM_ENCRYPTION_KEY`

## Recommended rollout

### Path A: Template-first (recommended)

1. Create a Zeabur template from this repository's `template.yaml`
2. Deploy the template so `web`, `api`, `worker`, `postgresql`, and `redis` come up together
3. Fill the required variables in Zeabur secrets
4. Run `pnpm deploy:db` against the production `DATABASE_URL`
5. Restart `api` and `worker`
6. Verify `/admin` shows `Readiness = ready`

### Path B: Raw GitHub import (fallback)

1. Create managed PostgreSQL in Zeabur
2. Create managed Redis in Zeabur
3. Deploy `api`, `worker`, and `web` separately from this GitHub repo with their respective Dockerfiles
4. Fill env vars from `.env.zeabur.production.example`
5. Run `pnpm deploy:db`
6. Verify the admin console shows `ready`

## Backup policy

- Daily PostgreSQL dump with `scripts/backup-postgres.sh`
- Store dumps in offsite storage
- Keep Redis as disposable queue/cache state

## Deploy Button note

Zeabur `Deploy Button` requires a Zeabur template entry first. After you create the template from `template.yaml`, you can generate a reusable Deploy Button in the Zeabur dashboard and paste it into `README.md`.

## Rebuild V1 references

- `docs/zeabur-rebuild-v1.md`
- `docs/rebuild-v1-release-checklist.md`
- `docs/rebuild-v1-deploy-runbook.md`
