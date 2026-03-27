# Zeabur Phase 1 Topology

## Planned Services

- `web` — Next.js 15 frontend
- `api` — FastAPI service
- `worker` — Celery worker
- `postgres` — PostgreSQL
- `redis` — Redis

## Minimum environment variables

### Web

- `NEXT_PUBLIC_API_BASE_URL`
- `AUTH_SECRET`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `CASDOOR_ENDPOINT`

### API / Worker

- `DATABASE_URL`
- `REDIS_URL`
- `SYSTEM_ENCRYPTION_KEY`
- `CASDOOR_ENDPOINT`
- `CASDOOR_CLIENT_ID`

## Deployment sequence

1. PostgreSQL
2. Redis
3. API
4. Worker
5. Web

## Notes

- Phase 1 only delivers the skeleton. Business capability migration comes later.
- The existing Streamlit app remains the current production system until the new stack is feature-complete.
