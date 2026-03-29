# Rebuild v1 Deploy Runbook

## 1. Prepare environment

- Copy `.env.rebuild.production.example`
- Fill database, Redis, Casdoor, secret, and team access values
- Put at least one Casdoor user email into `TEAM_ADMIN_EMAILS`
- Set `TEAM_ALLOWED_EMAIL_DOMAINS` for the team tenant boundary

## 2. Prepare database

- Run `pnpm prisma:validate`
- Set `AUTO_BOOTSTRAP_DB=true` on the API service for first deploy
- Let API startup create missing SQLAlchemy tables and seed `system@xiaobaitu.local`
- Run `pnpm deploy:db` only for Prisma-led schema upgrades after initial bootstrap

## 3. Start services

- Start PostgreSQL
- Start Redis
- Start API
- Start Worker
- Start Web
- Keep `AUTO_BOOTSTRAP_DB=false` on the worker

## 4. Verify runtime

- Open `/admin`
- Confirm `Readiness` shows `ready`
- Confirm no blocking warnings remain
- Confirm `active_backend=database`
- Confirm `active_execution_backend=celery`
- Confirm runtime shows `Casdoor` as auth provider
- Confirm default models show the `gemini-3.1-*` release values

## 5. Smoke test

```bash
python3 scripts/rebuild_release_smoke.py --api-base http://localhost:8000 --web-base http://localhost:3000
```

如果你要校验受保护的运行态接口，请再提供一个 Casdoor 管理员 token：

```bash
python3 scripts/rebuild_release_smoke.py --api-base http://localhost:8000 --web-base http://localhost:3000 --api-bearer-token "$API_BEARER_TOKEN" --require-ready
```

For production cutover:

```bash
python3 scripts/rebuild_release_smoke.py --api-base https://your-api-domain.example.com --web-base https://your-web-domain.example.com --api-bearer-token "$API_BEARER_TOKEN" --require-ready
```

## 6. Functional spot checks

- Sign in through Casdoor
- Open `/title` and submit one task
- Open `/translate` and verify default models
- Open `/quick` and `/batch` and verify default image model
- Open `/tasks` and confirm status updates
- Open `/tasks/[jobId]` and confirm timeline and structured result
- Open `/admin` and confirm no blocking warnings

## 7. Cutover rule

- Only switch traffic after readiness is `ready`
- If runtime falls back to `memory` or `inline`, stop cutover and fix infra first
- Release tag for this line is `rebuild-v1.0.0`
