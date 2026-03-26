# Zeabur Template-First Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make this repository deployable on Zeabur through a template-first flow that provisions app, PostgreSQL, and Redis with minimal manual setup.

**Architecture:** Add a repository-level `template.yaml`, keep the current Dockerfile app service, wire database/cache variables from Zeabur service exposures, and improve startup diagnostics so the login page explains exactly why team mode is unavailable. Install the requested UI skill locally only after deployment work is stable.

**Tech Stack:** Streamlit, Python, SQLAlchemy, Alembic, PostgreSQL, Redis, Zeabur Template YAML, Dockerfile-based Git deployment.

---

### Task 1: Add failing diagnostics tests

**Files:**
- Create: `tests/test_platform_deploy_diagnostics.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

import app


class PlatformDeployDiagnosticsTest(unittest.TestCase):
    def test_missing_database_url_status_message(self):
        status = {
            "configured": False,
            "reachable": False,
            "missing_tables": [],
            "error": "",
        }
        info = app.describe_platform_database_status(status)
        self.assertEqual(info["state"], "missing_database_url")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `".venv/bin/python" -m unittest tests/test_platform_deploy_diagnostics.py`
Expected: FAIL because `describe_platform_database_status` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a helper in `app.py` that maps raw DB status into explicit states and user-facing messages.

- [ ] **Step 4: Run test to verify it passes**

Run: `".venv/bin/python" -m unittest tests/test_platform_deploy_diagnostics.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_platform_deploy_diagnostics.py
git commit -m "test: add database readiness diagnostics"
```

### Task 2: Add Zeabur template

**Files:**
- Create: `template.yaml`
- Modify: `README.md`
- Modify: `docs/zeabur-production.md`

- [ ] **Step 1: Create Zeabur template YAML**

Define `temu-app`, `postgresql`, and `redis`, with app dependencies and exposed variables.

- [ ] **Step 2: Verify expected env mapping exists**

Check that `DATABASE_URL=${POSTGRES_CONNECTION_STRING}` and `REDIS_URL=${REDIS_CONNECTION_STRING}` are present.

- [ ] **Step 3: Document template-first deployment**

Update docs to mark the template path as the recommended Zeabur route.

- [ ] **Step 4: Review README deployment section**

Ensure fallback GitHub import remains documented, but secondary.

- [ ] **Step 5: Commit**

```bash
git add template.yaml README.md docs/zeabur-production.md
git commit -m "feat: add Zeabur template-first deployment"
```

### Task 3: Improve login/admin diagnostics

**Files:**
- Modify: `app.py`
- Modify: `temu_core/streamlit_admin.py`

- [ ] **Step 1: Use the new diagnostics helper in login page**
- [ ] **Step 2: Use the same diagnostics helper in admin status messaging**
- [ ] **Step 3: Keep fallback behavior unchanged, only improve visibility**
- [ ] **Step 4: Run smoke checks**

Run: `".venv/bin/python" -m py_compile app.py temu_core/streamlit_admin.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/streamlit_admin.py
git commit -m "feat: clarify Zeabur database readiness messages"
```

### Task 4: Install UI skill locally

**Files:**
- Create: local OpenCode skill directories under `~/.config/opencode/skills/`
- Do not modify production deployment files

- [ ] **Step 1: Install vetted skill locally only**
- [ ] **Step 2: Verify the skill files exist under OpenCode config**
- [ ] **Step 3: Record local-only usage rule for future UI refactors**

### Task 5: Final verification

**Files:**
- None new

- [ ] **Step 1: Run unit tests**

Run: `".venv/bin/python" -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 2: Run migration/seeding integration check**

Run the SQLite smoke setup used in earlier deployment verification.
Expected: PASS.

- [ ] **Step 3: Run Streamlit health check**

Run the headless health probe against `/_stcore/health`.
Expected: `ok`.

- [ ] **Step 4: Commit and push**

```bash
git add .
git commit -m "feat: add Zeabur template deployment path"
git push origin main
```
