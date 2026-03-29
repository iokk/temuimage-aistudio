# Administrator Manual

## Purpose

This manual covers the operational flow for the official rebuild release `rebuild-v1.0.0`.

## Core responsibilities

- Maintain Casdoor as the only formal login entrypoint
- Keep `TEAM_ADMIN_EMAILS` aligned with real platform administrators
- Keep `TEAM_ALLOWED_EMAIL_DOMAINS` aligned with the team boundary
- Keep PostgreSQL and Redis healthy
- Watch `/admin` before and after releases

## Sign-in policy

- All formal operators sign in through Casdoor
- API access is validated with Casdoor bearer tokens
- Bootstrap login is not part of the official release path

## Runtime checks

Open `/admin` and confirm:

- `auth_provider = Casdoor`
- `active_backend = database`
- `active_execution_backend = celery`
- `ready_for_distributed_workers = true`
- Default models match the release policy

## Release policy defaults

- Title model: `gemini-3.1-pro`
- Translate analysis model: `gemini-3.1-pro`
- Translate image model: `gemini-3.1-flash-image-preview`
- Quick image model: `gemini-3.1-flash-image-preview`
- Batch image model: `gemini-3.1-flash-image-preview`

## First-line diagnostics

If `/admin` shows degraded status:

1. Check `DATABASE_URL`
2. Check `REDIS_URL`
3. Check `JOB_STORE_BACKEND=database`
4. Check `ASYNC_JOB_BACKEND=celery`
5. Check Casdoor issuer and client envs
6. Check `TEAM_ADMIN_EMAILS`

## Database operations

- First deploy uses `AUTO_BOOTSTRAP_DB=true` on `api`
- Worker must keep `AUTO_BOOTSTRAP_DB=false`
- Use `pnpm deploy:db` only for Prisma-managed schema upgrades

## Zeabur operations

- Keep five services: `web`, `api`, `worker`, `postgresql`, `redis`
- Expose only `web` and `api` publicly
- Keep `NEXT_PUBLIC_API_BASE_URL` pointed at the public API domain
- Keep `NEXTAUTH_URL` pointed at the public web domain

## Release checklist

- Run `pnpm build:web`
- Run `pnpm prisma:validate`
- Run focused Python compile checks
- Run `scripts/rebuild_release_smoke.py` with a short-lived admin Casdoor token
- Tag the release as `rebuild-v1.0.0`
