# Zeabur V1 Topology

## Planned Services

- `web` — Next.js 15 frontend
- `api` — FastAPI service
- `worker` — Celery worker
- `postgres` — PostgreSQL
- `redis` — Redis

## Minimum environment variables

### Web

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `CASDOOR_ISSUER`

### API / Worker

- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `API_APP_NAME`
- `API_APP_VERSION`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`
- `SYSTEM_ENCRYPTION_KEY`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`

## Deployment sequence

1. PostgreSQL
2. Redis
3. API
4. Worker
5. Web

## V1 readiness rules

- `Celery` only should be used with persistent job storage
- If `JOB_STORE_BACKEND` stays on `memory`, the API will force async execution back to `inline`
- Run `pnpm deploy:db` before bringing API / Worker online
- Confirm the admin runtime panel shows no blocking warnings before switching traffic
