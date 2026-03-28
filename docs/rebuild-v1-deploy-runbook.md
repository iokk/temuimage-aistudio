# Rebuild V1 Deploy Runbook

## 1. Prepare env

- Copy `.env.rebuild.production.example`
- Fill Casdoor, database, Redis, secrets, and team admin values

## 2. Prepare database

- Run `pnpm prisma:validate`
- Run `pnpm deploy:db`
- Confirm the `system` user seed completed

## 3. Start services

- Start PostgreSQL
- Start Redis
- Start API
- Start Worker
- Start Web

## 4. Verify runtime

- Open `/admin`
- Confirm `Readiness` shows `ready`
- Confirm no blocking warnings remain
- Confirm `active_backend=database`
- Confirm `active_execution_backend=celery`

## 5. Smoke test

- Run:

```bash
python3 scripts/rebuild_release_smoke.py --api-base http://localhost:8000 --web-base http://localhost:3000
```

- For production cutover, use:

```bash
python3 scripts/rebuild_release_smoke.py --api-base https://your-api-domain.example.com --web-base https://your-web-domain.example.com --require-ready
```

## 6. Functional spot checks

- Login through Casdoor
- Open `/title` and submit one task
- Open `/tasks` and confirm status updates
- Open `/tasks/[jobId]` and confirm timeline + structured result
- Open `/admin` and confirm no blocking warnings

## 7. Cutover rule

- Only switch traffic after readiness is `ready`
- If runtime falls back to `memory` or `inline`, stop cutover and fix infra first
