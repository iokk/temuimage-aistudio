# Zeabur Production Plan

## Target topology

- `temu-app` on Zeabur
- managed PostgreSQL
- managed Redis
- S3-compatible object storage

The app should remain stateless. Persistent business state must not depend on `/app/data`.

## Required env vars

- `DATABASE_URL`
- `REDIS_URL`
- `PLATFORM_AUTO_MIGRATE=true`
- `PLATFORM_SEED_DEFAULTS=true`
- `PLATFORM_DEFAULT_ORG_NAME`
- `PLATFORM_ENCRYPTION_KEY`
- `S3_ENDPOINT`
- `S3_BUCKET`
- `S3_REGION`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`

## Recommended rollout

1. Create managed PostgreSQL in Zeabur
2. Create managed Redis in Zeabur
3. Connect object storage credentials
4. Deploy app with `PLATFORM_AUTO_MIGRATE=true`
5. Verify the admin console shows the team database as ready
6. Create the first organization wallet adjustment and redeem-code batch

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
