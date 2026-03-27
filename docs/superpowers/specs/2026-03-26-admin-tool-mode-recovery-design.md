# Admin Tool Mode Recovery Design

## Goal

Recover the product into a stable administrator-first tool when `DATABASE_URL` is absent, so core features remain usable without team-mode dependencies.

## Scope

- Hide all team-mode specific entry points when no database is configured.
- Keep administrator login and backend access always available.
- Unify credential selection for user/system Gemini and relay usage.
- Restore usability for pages 1/2/3/4 under administrator tool mode.
- Remove conflicting or dead legacy UI/config branches that block usage.

## Product Rule

When `DATABASE_URL` is missing, the product must behave as an administrator tool system, not a partially broken team app.

- Show: admin login, system config, own credential config, batch image generation, quick generation, title optimization, image translation
- Hide: registration, wallets, projects, pricing rules, redeem codes, team-user management, team-only notices

## Design Decisions

1. Introduce a single runtime mode resolver that classifies the app into `admin_tool_mode` or `team_mode`.
2. Introduce a single credential resolver that returns the active runtime provider and credentials for each feature.
3. Make dashboard cards and admin entry explicit interactive controls.
4. Prefer one clear config surface for personal credentials and one for system credentials.
5. Clean up old parallel branches only after the new admin-tool path is verified.

## Success Criteria

- Without a database, users can still log in as admin and use 1/2/3/4.
- Admin can always enter backend configuration.
- No dead buttons or hidden-gate confusion for core actions.
- Team-specific features are invisible until database mode is truly enabled.
