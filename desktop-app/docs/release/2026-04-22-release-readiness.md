# Release Readiness

- Date: 2026-04-22
- Product: `EcommerceWorkbenchDesktop`
- Target: macOS arm64 distribution

## Current Status

The desktop app is now in release-prep shape:

1. The renderer is bundled into packaged app resources.
2. The Python application bundle is bundled into packaged app resources.
3. A copied Python 3.12 runtime is bundled into packaged app resources.
4. The packaged `.app` has been smoke-tested and can start the bundled FastAPI service.
5. `package` and `make` flows both complete successfully.

## Core Artifacts

Current expected distribution outputs:

1. `client/electron/out/EcommerceWorkbenchDesktop-darwin-arm64/EcommerceWorkbenchDesktop.app`
2. `client/electron/out/make/EcommerceWorkbenchDesktop-0.1.0-arm64.dmg`
3. `client/electron/out/make/zip/darwin/arm64/EcommerceWorkbenchDesktop-darwin-arm64-0.1.0.zip`

## Required Packaged Resources

The app bundle should contain:

1. `Contents/Resources/renderer/index.html`
2. `Contents/Resources/python-bundle/main.py`
3. `Contents/Resources/python-bundle/runtime-manifest.json`
4. `Contents/Resources/python-runtime/bin/python3.12`
5. `Contents/Resources/python-runtime/runtime-manifest.json`

## Release Commands

From `desktop-app/`:

```bash
npm run prepare:assets
npm run package:electron
npm run make:electron
npm run release:report
```

## Remaining Release Tasks

The core engineering work is done, but these release steps still matter:

1. Run a full success-path workflow using a real provider key.
2. Replace the generic Electron icon and polish app branding.
3. Add signing configuration.
4. Notarize the app or DMG.
5. Staple the notarization ticket.
6. Validate install/startup on a clean machine.

## Signing And Notarization Checklist

Recommended macOS release path:

1. Confirm a stable bundle identifier.
2. Add signing credentials to the local release machine.
3. Sign the packaged `.app`.
4. Submit to Apple notarization.
5. Staple the notarization ticket.
6. Re-run smoke tests on the stapled artifact.

Typical secret inputs:

1. `APPLE_ID`
2. `APPLE_TEAM_ID`
3. `APPLE_APP_SPECIFIC_PASSWORD`

Alternative `notarytool` API key route:

1. App Store Connect API key id
2. Issuer id
3. Private key `.p8`

## Manual QA Checklist

Before shipping externally, verify:

1. App launches from Finder.
2. App writes data under `~/Library/Application Support/EcommerceWorkbenchDesktop`.
3. Provider save/test works.
4. Title generation succeeds with a real key.
5. Image translation succeeds with a real key.
6. Quick generation succeeds with a real key.
7. Smart generation succeeds with a real key.
8. Project trash / restore / purge still behave correctly.
