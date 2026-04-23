#!/bin/zsh
set -euo pipefail

DMG_PATH="${1:-}"

if [[ -z "${DMG_PATH}" ]]; then
  echo "Usage: scripts/notarize-macos-dmg.sh <path-to-dmg>" >&2
  exit 1
fi

if [[ ! -f "${DMG_PATH}" ]]; then
  echo "DMG not found: ${DMG_PATH}" >&2
  exit 1
fi

if [[ -z "${APPLE_ID:-}" || -z "${APPLE_TEAM_ID:-}" || -z "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
  echo "Missing notarization environment variables." >&2
  echo "Required: APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD" >&2
  exit 1
fi

echo "Submitting DMG for notarization..."
xcrun notarytool submit \
  "${DMG_PATH}" \
  --apple-id "${APPLE_ID}" \
  --team-id "${APPLE_TEAM_ID}" \
  --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
  --wait

echo "Stapling notarization ticket..."
xcrun stapler staple "${DMG_PATH}"

echo "Notarization complete."
