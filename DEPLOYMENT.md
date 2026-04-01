# XiaoBaiTu Rebuild v1.0.0 Deployment

## Release path

`rebuild-v1.0.0` ships only on the rebuild stack:

1. `web`
2. `api`
3. `worker`
4. `postgresql`
5. `redis`

The old Streamlit stack remains archived and is not part of the production deploy path.

## Identity requirement

- Casdoor is mandatory
- Bootstrap login is no longer an official deploy path
- `TEAM_ADMIN_EMAILS` must contain at least one Casdoor user email

## Recommended deployment

Use `template.yaml` on Zeabur.

Do not point Zeabur at the repository root `Dockerfile` for the rebuild release. The root Dockerfile still starts the archived Streamlit app; rebuild production must use `template.yaml` or the service Dockerfiles in `apps/`.

## Validation before deploy

```bash
pnpm build:web
pnpm prisma:validate
python3 -m py_compile apps/api/core/auth.py apps/api/job_repository.py apps/api/routers/jobs.py apps/api/routers/system.py apps/api/routers/title.py apps/api/routers/quick.py apps/api/routers/batch.py apps/api/routers/translate.py apps/api/task_processor.py apps/api/bootstrap_db.py apps/api/db/models.py apps/api/core/config.py
```

## Required environment

### Web

- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `NEXT_PUBLIC_API_BASE_URL`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`

### API and Worker

- `DATABASE_URL`
- `REDIS_URL`
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `AUTO_BOOTSTRAP_DB=true` on `api`
- `AUTO_BOOTSTRAP_DB=false` on `worker`
- `API_APP_VERSION=1.0.0`
- `CASDOOR_ISSUER`
- `CASDOOR_CLIENT_ID`
- `CASDOOR_CLIENT_SECRET`
- `CASDOOR_API_AUDIENCE` when your Casdoor access token uses a custom audience
- `SYSTEM_ENCRYPTION_KEY`
- `TEAM_ADMIN_EMAILS`
- `TEAM_ALLOWED_EMAIL_DOMAINS`

## First startup

1. Start `postgresql`
2. Start `redis`
3. Start `api`
4. Start `worker`
5. Start `web`
6. Let `api` create SQLAlchemy tables and seed `system@xiaobaitu.local`
7. Run `pnpm deploy:db` only for Prisma-managed upgrades

## Post-deploy checks

1. Open `/login` and confirm Casdoor redirects correctly
2. Open `/admin`
3. Confirm `Readiness = ready`
4. Confirm `active_backend = database`
5. Confirm `active_execution_backend = celery`
6. Confirm runtime default models show the `gemini-3.1-*` values

## Related docs

- `docs/zeabur-rebuild-v1.md`
- `docs/rebuild-v1-deploy-runbook.md`
- `docs/rebuild-v1-release-checklist.md`
- `docs/admin-manual.md`
