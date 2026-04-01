# XiaoBaiTu Rebuild v1.0.0

XiaoBaiTu Rebuild is the official release path for the product. The formal `rebuild-v1.0.0` release ships a multi-service stack with `web`, `api`, `worker`, `postgresql`, and `redis`, and uses Casdoor as the only formal identity entrypoint.

## Official stack

- `apps/web` - Next.js 15 frontend
- `apps/api` - FastAPI application API
- `apps/worker` - Celery worker
- `packages/db` - Prisma schema and migrations
- `template.yaml` - Zeabur multi-service template

## Release defaults

- Title model: `gemini-3.1-pro`
- Translate image model: `gemini-3.1-flash-image-preview`
- Translate analysis model: `gemini-3.1-pro`
- Quick image model: `gemini-3.1-flash-image-preview`
- Batch image model: `gemini-3.1-flash-image-preview`
- Release tag: `rebuild-v1.0.0`

## Identity

- Formal sign-in path: Casdoor OIDC only
- Web keeps `Auth.js` as the session layer
- API verifies Casdoor bearer tokens directly
- Team admin access is controlled by `TEAM_ADMIN_EMAILS`
- Team membership is controlled by `TEAM_ALLOWED_EMAIL_DOMAINS`

## Zeabur deploy

Use the template-first path.

Do not deploy the repository root `Dockerfile` for `rebuild-v1.0.0`. That file starts the archived Streamlit stack; the official rebuild release path is `template.yaml` or the per-service Dockerfiles under `apps/`.

1. Deploy `template.yaml`
2. Fill Casdoor, team, and secret variables
3. Wait for `postgresql`, `redis`, `api`, `worker`, and `web`
4. Sign in through Casdoor
5. Verify `/admin` shows the runtime as ready

### Deploy Button placeholder

After you publish `template.yaml` as a Zeabur Template and copy the button from `Account -> Template -> Share`, replace the placeholder below with the real template code:

```md
[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/<template-code>)
```

`<template-code>` must come from the published Zeabur Template URL, not from the GitHub repository URL. The full publishing flow lives in `docs/zeabur-auto-deploy.md`.

Primary docs:

- `docs/zeabur-rebuild-v1.md`
- `docs/zeabur-auto-deploy.md`
- `docs/rebuild-v1-release-checklist.md`
- `docs/rebuild-v1-deploy-runbook.md`
- `docs/admin-manual.md`

## Local validation

```bash
pnpm build:web
pnpm prisma:validate
python3 -m py_compile apps/api/core/auth.py apps/api/job_repository.py apps/api/routers/jobs.py apps/api/routers/system.py apps/api/routers/title.py apps/api/routers/quick.py apps/api/routers/batch.py apps/api/routers/translate.py apps/api/task_processor.py apps/api/bootstrap_db.py apps/api/db/models.py apps/api/core/config.py
```

## Legacy archive

The old Streamlit stack is preserved as project history and backup only. It is no longer the official release or deployment path.

Archive-era files include:

- `app.py`
- `temu_core/`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `scripts/deploy-zeabur.sh`
- `scripts/deploy-debian.sh`

## Repository

`https://github.com/iokk/temuimage-aistudio`
