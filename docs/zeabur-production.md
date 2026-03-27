# Zeabur Production Plan

## Target topology

- `temu-app` on Zeabur
- managed PostgreSQL
- managed Redis
- S3-compatible object storage

Repository-shipped `template.yaml` is now the recommended deployment entrypoint.

The app should remain stateless. Persistent business state must not depend on `/app/data`.

## Required env vars

- `DATABASE_URL`
- `REDIS_URL`
- `PLATFORM_AUTO_MIGRATE=true`
- `PLATFORM_SEED_DEFAULTS=true`
- `PLATFORM_DEFAULT_ORG_NAME`
- `PLATFORM_DEFAULT_PROJECT_NAME`
- `PLATFORM_ENCRYPTION_KEY`
- `TITLE_TEXT_MODEL=gemini-3.1-pro`
- `S3_ENDPOINT`
- `S3_BUCKET`
- `S3_REGION`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`

## Recommended rollout

### Path A: Template-first (recommended)

1. Create a Zeabur template from this repository's `template.yaml`
2. Deploy the template so `temu-app`, `postgresql`, and `redis` come up together
3. Fill only the required variables:
   - `SYSTEM_API_KEYS_FIXED`
   - `ADMIN_PASSWORD_FIXED`
   - `PLATFORM_ENCRYPTION_KEY`
4. Wait for the app to start with `PLATFORM_AUTO_MIGRATE=true`
5. Verify the login page shows team auth as ready, not fallback mode

### Path B: Raw GitHub import (fallback)

1. Create managed PostgreSQL in Zeabur
2. Create managed Redis in Zeabur
3. Connect object storage credentials if needed
4. Deploy app with `DATABASE_URL`, `REDIS_URL`, `PLATFORM_AUTO_MIGRATE=true`, and `PLATFORM_SEED_DEFAULTS=true`
5. Verify the admin console shows the team database as ready

## Backup policy

- Daily PostgreSQL dump with `scripts/backup-postgres.sh`
- Store dumps in offsite object storage
- Retention target: 7 daily, 4 weekly, 3 monthly
- Export `wallet_ledger_entries`, `redeem_codes`, and `usage_events` periodically for audit recovery

## Restore checklist

1. Restore PostgreSQL from the latest verified dump
2. Restore object storage artifacts if needed
3. Re-run `python3 -m alembic upgrade head`
4. Verify wallet balance totals against ledger sums

## Deploy Button note

Zeabur `Deploy Button` requires a Zeabur template entry first. After you create the template from `template.yaml`, you can generate a reusable Deploy Button in the Zeabur dashboard and paste it into `README.md`.

## Post-deploy checklist

After every Zeabur deployment, run the product validation checklist in:

`docs/post-deploy-checklist.md`
