# Team Billing Foundation

This repository now includes the first shared-billing foundation for the future team web product.

## What is included

- PostgreSQL-ready SQLAlchemy models under `temu_core/`
- Alembic migrations under `alembic/`
- Admin wallet adjustments and redeem-code batch generation in the existing Streamlit admin console
- Usage-event capture hooks for the current generation flows
- Zeabur-ready environment variables for managed PostgreSQL, Redis, and object storage

## Current scope

This commit starts the platform migration without breaking the current monolith.

- Existing JSON files still power legacy settings, users, and usage limits
- New shared-billing state is designed to live in PostgreSQL only
- Wallet charging is not yet enforcing runtime spend limits
- The default organization is seeded as `TEMU Team Workspace`

## Core tables

- `organizations`
- `projects`
- `wallet_accounts`
- `wallet_ledger_entries`
- `admin_topups`
- `redeem_code_batches`
- `redeem_codes`
- `redeem_code_redemptions`
- `usage_events`
- `pricing_rules`
- `audit_logs`

## Local bootstrap

1. Set `DATABASE_URL`
2. Run `python3 -m alembic upgrade head`
3. Run `python3 scripts/seed_platform_defaults.py`

## Next milestones

1. Replace JSON user/session identity with real organizations and members
2. Attach project context to generation actions
3. Start debiting organization wallets from usage events
4. Add personal wallets and BYOK policy switching
