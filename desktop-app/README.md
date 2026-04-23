# Ecommerce Workbench Desktop

这个目录是 `desktop/mac` 运行形态的实验桌面壳。

当前仓库主线仍然是根目录下的 Streamlit 应用，但桌面端代码保留在这里，作为后续把同一套个人工作台能力封装成 macOS 原生桌面应用的基础。

## What exists today

1. Electron desktop shell
2. React/Vite renderer startup screen
3. Local Python service skeleton
4. Runtime health-check chain between Electron and local backend

## Quick start

```bash
cd desktop-app
npm install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
npm run dev
```

The renderer runs on `http://127.0.0.1:5173` in development and Electron launches the local FastAPI service on port `8765` by default.

## Runtime baseline

The desktop app now targets Python `3.12` for local development and future packaging work.

Why:

1. `google-genai` is already warning on Python 3.9 EOL.
2. The system `python3` on this machine is linked against `LibreSSL`, which is not a good long-term baseline for the desktop runtime.
3. We want the dev runtime to match the eventual bundled runtime more closely.

## Packaging readiness

The project now supports a staged packaging flow:

```bash
npm run prepare:assets
npm run package:electron
npm run make:electron
npm run release:report
```

What this does:

1. Builds the renderer into `.dist/renderer`
2. Copies the Python app into `.dist/python-bundle`
3. Creates a standalone copied venv in `.dist/python-runtime`
4. Runs Electron Forge package
5. Verifies the packaged app contains the required desktop resources
6. Can produce DMG / ZIP artifacts and print release checksums

## Signing helpers

Signing and notarization helpers are now included:

```bash
export APPLE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
npm run release:sign-app

export APPLE_ID="you@example.com"
export APPLE_TEAM_ID="TEAMID"
export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
npm run release:notarize-dmg
```

Current packaged resources target this structure inside the app bundle:

1. `Resources/renderer`
2. `Resources/python-bundle`
3. `Resources/python-runtime`
