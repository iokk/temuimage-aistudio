# Team Billing Foundation

This repository now includes the first shared-billing foundation for the future team web product.

## What is included

- PostgreSQL-ready SQLAlchemy models under `temu_core/`
- Alembic migrations under `alembic/`
- Admin wallet adjustments and redeem-code batch generation in the existing Streamlit admin console
- Team workspace provisioning for organizations, members, and projects
- Usage-event capture plus shared-wallet debits for the current generation flows
- Registered user accounts with admin-managed disable/delete backups
- Encrypted system API key storage when `PLATFORM_ENCRYPTION_KEY` is configured
- Zeabur-ready environment variables for managed PostgreSQL, Redis, and object storage
- A repository-level `template.yaml` for template-first Zeabur deployment

## Current scope

This commit starts the platform migration without breaking the current monolith.

- Existing JSON files still power legacy settings, users, and usage limits
- New shared-billing state is designed to live in PostgreSQL only
- Wallet charging now records shared-wallet debits from pricing rules, but it does not hard-block low balance yet to avoid breaking the legacy flow
- The default organization is seeded as `TEMU Team Workspace`
- The default project is seeded as `Default Project`
- Title optimization defaults to the Gemini text path `gemini-3.1-pro`
- Pages 1/2/3/4 are intended to run under registered user accounts when the team database is ready

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
- `platform_configs`
- `user_backups`
- `audit_logs`

## Local bootstrap

1. Set `DATABASE_URL`
2. Run `python3 -m alembic upgrade head`
3. Run `python3 scripts/seed_platform_defaults.py`
4. Set `PLATFORM_ENCRYPTION_KEY` before storing system API Keys in production
5. Open the admin console and verify `注册用户管理`, `团队工作区`, `定价规则`, `钱包账本`, and `兑换码` tabs

## Zeabur template-first deployment

Use `template.yaml` when possible so Zeabur provisions:

- `temu-app`
- `postgresql`
- `redis`

This avoids the most common production issue: the login page falling back because `DATABASE_URL` or migrations were never set up.

## Next milestones

1. Replace the remaining legacy fallback login paths with invite-only team auth
2. Add personal wallets and BYOK policy switching
3. Enforce low-balance cutoff after the shared wallet is funded in production
4. Expand project-level billing/reporting dashboards
