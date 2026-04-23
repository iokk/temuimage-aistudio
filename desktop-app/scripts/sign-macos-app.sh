#!/bin/zsh
set -euo pipefail

APP_PATH="${1:-}"

if [[ -z "${APP_PATH}" ]]; then
  echo "Usage: scripts/sign-macos-app.sh <path-to-app>" >&2
  exit 1
fi

if [[ ! -d "${APP_PATH}" ]]; then
  echo "App not found: ${APP_PATH}" >&2
  exit 1
fi

if [[ -z "${APPLE_SIGN_IDENTITY:-}" ]]; then
  echo "Missing APPLE_SIGN_IDENTITY" >&2
  echo "Example: export APPLE_SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'" >&2
  exit 1
fi

ENTITLEMENTS_PATH="${APPLE_ENTITLEMENTS_PATH:-}"

CMD=(
  codesign
  --force
  --deep
  --options
  runtime
  --sign
  "${APPLE_SIGN_IDENTITY}"
)

if [[ -n "${ENTITLEMENTS_PATH}" ]]; then
  CMD+=(--entitlements "${ENTITLEMENTS_PATH}")
fi

CMD+=("${APP_PATH}")

echo "Signing app with identity: ${APPLE_SIGN_IDENTITY}"
"${CMD[@]}"

echo "Verifying signature..."
codesign --verify --deep --strict --verbose=2 "${APP_PATH}"

echo "Signing complete."
