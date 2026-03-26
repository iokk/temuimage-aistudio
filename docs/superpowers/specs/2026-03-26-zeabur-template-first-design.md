# Zeabur Template-First Deployment Design

## Goal

Make the repository deployable on Zeabur through a template-first path so the app, PostgreSQL, and Redis come up together with minimal manual setup.

## Context

- The app already supports a PostgreSQL-backed team/auth/billing foundation.
- Current GitHub import on Zeabur still falls back to legacy login when `DATABASE_URL` is missing, unreachable, or migrations were not applied.
- The owner wants a near one-click deployment path and does not want secrets committed to GitHub.

## Recommended Approach

Use a repository-shipped `template.yaml` as the primary deployment artifact, while keeping Dockerfile-based GitHub import as a fallback. The template should provision `temu-app`, `postgresql`, and `redis`, inject the database/cache connection strings into the app, and set safe defaults for auto-migration, seeding, and title generation.

## Why This Approach

- It removes the most common deployment failure: missing database variables.
- It keeps secrets out of the repository by asking for only a few deploy-time variables.
- It preserves the current app runtime and avoids a large architectural rewrite.

## Service Topology

- `temu-app`: Git-based service using the current repository and Dockerfile
- `postgresql`: Zeabur prebuilt PostgreSQL service exposing `POSTGRES_CONNECTION_STRING`
- `redis`: Zeabur prebuilt Redis service exposing `REDIS_CONNECTION_STRING`

`temu-app` depends on both database services so startup order is deterministic.

## Default App Variables

- `DATABASE_URL=${POSTGRES_CONNECTION_STRING}`
- `REDIS_URL=${REDIS_CONNECTION_STRING}`
- `PLATFORM_AUTO_MIGRATE=true`
- `PLATFORM_SEED_DEFAULTS=true`
- `PLATFORM_DEFAULT_ORG_NAME=TEMU Team Workspace`
- `PLATFORM_DEFAULT_PROJECT_NAME=Default Project`
- `TITLE_TEXT_MODEL=gemini-3.1-pro`

## Deploy-Time Variables

- `SYSTEM_API_KEYS_FIXED`
- `ADMIN_PASSWORD_FIXED`
- `PLATFORM_ENCRYPTION_KEY`
- `PUBLIC_DOMAIN` (optional)

## Diagnostics Improvement

Replace the generic database warning with explicit states:

1. `DATABASE_URL` missing
2. Database unreachable
3. Database reachable but team tables missing

These messages should appear on the login page and in the admin platform status area.

## UI Skill Handling

The requested `nextlevelbuilder/ui-ux-pro-max-skill` should be installed locally only, not wired into production deployment. It can be used for future UI refactors after the deployment path is stable.

## Non-Goals

- No change to overseas production networking; local proxy remains local-only.
- No secret values committed to Git.
- No large UI redesign in this deployment pass.
