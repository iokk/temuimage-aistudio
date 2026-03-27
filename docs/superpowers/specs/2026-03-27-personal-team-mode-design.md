# Personal and Team Mode Refactor Design

## Goal

Restructure the product around two explicit modes — personal and team — so feature access and configuration make sense before doing a second pass on provider/model reliability checks.

## Product Modes

### Personal Mode

- User enters with personal credentials
- Supports:
  - personal Gemini key
  - personal relay URL / key / model
- No guest mode

### Team Mode

- Official account / registered login
- Admin backend remains the system configuration surface
- Team members use system Gemini / system relay as controlled by administrators

### No Database Behavior

When `DATABASE_URL` is absent:

- Team registration flow is hidden
- Team-only management stays hidden
- Product still works in admin-tool / personal mode

## Refactor Priorities

1. Simplify login and mode selection
2. Separate personal credentials from team/system credentials
3. Keep navigation stable and all four major tools visible
4. Only after that, add provider/model preflight checks to reduce runtime crashes

## Functional Reliability Follow-up

After the mode refactor, add provider/model prechecks to pages 1/2/3/4 so unsupported relay/Gemini flows are blocked before execution with clear user-facing messages.
