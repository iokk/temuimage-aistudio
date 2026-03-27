# Admin Tool Mode Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the product into a stable administrator tool system whenever `DATABASE_URL` is missing, while keeping pages 1/2/3/4 usable and configuration paths understandable.

**Architecture:** Add a runtime-mode resolver and a unified credential resolver, then route login, navigation, admin access, and core feature pages through those helpers. Hide team-mode surfaces completely when the app is running without a database, and simplify credential entry into clear personal/system sections.

**Tech Stack:** Streamlit, Python, helper modules under `temu_core/`, unittest, existing relay/Gemini integration.

---

### Task 1: Add runtime mode resolution

**Files:**
- Create: `temu_core/runtime_mode.py`
- Create: `tests/test_runtime_mode.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from temu_core.runtime_mode import get_runtime_mode, should_show_team_features


class RuntimeModeTest(unittest.TestCase):
    def test_missing_database_uses_admin_tool_mode(self):
        self.assertEqual(get_runtime_mode(False, False), "admin_tool_mode")
        self.assertFalse(should_show_team_features("admin_tool_mode"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `".venv/bin/python" -m unittest tests/test_runtime_mode.py`
Expected: FAIL because `temu_core.runtime_mode` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `temu_core/runtime_mode.py` with helpers:

```python
from __future__ import annotations


def get_runtime_mode(has_database_url: bool, team_ready: bool) -> str:
    if has_database_url and team_ready:
        return "team_mode"
    return "admin_tool_mode"


def should_show_team_features(runtime_mode: str) -> bool:
    return runtime_mode == "team_mode"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `".venv/bin/python" -m unittest tests/test_runtime_mode.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_runtime_mode.py temu_core/runtime_mode.py app.py
git commit -m "feat: add runtime mode resolver"
```

### Task 2: Restore admin entry and remove team-only blockers in admin mode

**Files:**
- Modify: `app.py`
- Modify: `temu_core/ui_content.py`
- Modify: `tests/test_ui_content.py`

- [ ] **Step 1: Write the failing test**

Add assertions that admin-tool mode messaging does not mention team gating as a blocker, and dashboard navigation metadata stays interactive and explicit.

- [ ] **Step 2: Run tests to verify failure**

Run: `".venv/bin/python" -m unittest tests/test_ui_content.py`
Expected: FAIL because current metadata and admin-mode wording are insufficient.

- [ ] **Step 3: Implement minimal fix**

Update `app.py` so that:
- when runtime mode is `admin_tool_mode`, registration/team paths are not rendered
- admin login remains visible and backend entry is always shown after admin auth
- dashboard cards/controls map to real page selections

Update `temu_core/ui_content.py` to return admin-tool-mode wording and page metadata that matches the new shell.

- [ ] **Step 4: Run tests to verify pass**

Run: `".venv/bin/python" -m unittest tests/test_ui_content.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/ui_content.py tests/test_ui_content.py
git commit -m "fix: keep admin mode usable without database"
```

### Task 3: Add unified credential resolver

**Files:**
- Create: `temu_core/credential_resolver.py`
- Create: `tests/test_credential_resolver.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from temu_core.credential_resolver import resolve_runtime_credentials


class CredentialResolverTest(unittest.TestCase):
    def test_prefers_user_relay_when_selected(self):
        result = resolve_runtime_credentials(
            runtime_mode="admin_tool_mode",
            use_own_key=False,
            own_gemini_key="",
            own_relay_key="user-key",
            own_relay_base="https://relay.example.com/v1",
            own_relay_model="gemini-3.1-flash-image-preview",
            system_gemini_key="AIzaSystem",
            system_relay_key="system-key",
            system_relay_base="https://relay.example.com/v1",
            system_relay_model="seedream-5.0",
            preferred_provider="relay",
            credential_scope="user",
        )
        self.assertEqual(result["provider"], "relay")
        self.assertEqual(result["api_key"], "user-key")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `".venv/bin/python" -m unittest tests/test_credential_resolver.py`
Expected: FAIL because resolver does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create resolver returning a normalized dict:

```python
{
    "provider": "relay" | "gemini",
    "scope": "user" | "system",
    "api_key": "...",
    "base_url": "...",
    "model": "...",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `".venv/bin/python" -m unittest tests/test_credential_resolver.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_credential_resolver.py temu_core/credential_resolver.py app.py
git commit -m "feat: unify runtime credential resolution"
```

### Task 4: Rebuild config surfaces into personal vs system sections

**Files:**
- Modify: `app.py`
- Modify: `temu_core/ui_content.py`

- [ ] **Step 1: Replace scattered credential inputs with two clear sections**
  - `我的凭据`: own Gemini key, own relay base/key/model
  - `系统配置`: system Gemini, system relay, default provider/model

- [ ] **Step 2: Remove duplicated relay config entry points from non-primary locations**

- [ ] **Step 3: Keep login/init path minimal for admin-tool mode**

- [ ] **Step 4: Verify syntax**

Run: `".venv/bin/python" -m py_compile app.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/ui_content.py
git commit -m "refactor: simplify personal and system config panels"
```

### Task 5: Restore 1/2/3/4 usability through unified runtime config

**Files:**
- Modify: `app.py`
- Modify: `temu_core/result_views.py` (create if needed)
- Modify: tests covering relay/title/runtime behavior as needed

- [ ] **Step 1: Route pages 1 and 2 through the resolver without team-mode gating**
- [ ] **Step 2: Route title optimization through the same resolver so relay/system config works coherently**
- [ ] **Step 3: Route image translation through the same resolver; if a provider is unsupported, show explicit supported-path messaging rather than a dead screen**
- [ ] **Step 4: Add/update regression tests for page-level gating helpers**
- [ ] **Step 5: Commit**

```bash
git add app.py tests
git commit -m "fix: restore core page usability in admin tool mode"
```

### Task 6: Remove dead/conflicting legacy UI logic

**Files:**
- Modify: `app.py`
- Modify: `temu_core/auth.py`
- Modify: `temu_core/relay_config.py`

- [ ] **Step 1: Remove or hide stale team-only branches when runtime mode is `admin_tool_mode`**
- [ ] **Step 2: Mark local JSON usage as admin-tool fallback rather than parallel primary logic**
- [ ] **Step 3: Remove redundant relay entry points left behind by the refactor**
- [ ] **Step 4: Run smoke checks**

Run: `".venv/bin/python" -m py_compile app.py temu_core/auth.py temu_core/relay_config.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/auth.py temu_core/relay_config.py
git commit -m "refactor: remove conflicting admin mode legacy branches"
```

### Task 7: Verification and release

**Files:**
- None new

- [ ] **Step 1: Run full unit test suite**

Run: `".venv/bin/python" -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 2: Run syntax verification**

Run: `".venv/bin/python" -m py_compile app.py temu_core/runtime_mode.py temu_core/credential_resolver.py temu_core/ui_content.py`
Expected: PASS.

- [ ] **Step 3: Run Streamlit health check**

Run a headless server and verify `/_stcore/health` returns `ok`.

- [ ] **Step 4: Manual smoke expectations**
  - No `DATABASE_URL` → admin tool mode only
  - Admin backend accessible
  - Pages 1/2/3/4 open and can be used
  - Personal Gemini, personal relay, and system relay paths all work without dead gates

- [ ] **Step 5: Commit and push**

```bash
git add .
git commit -m "fix: recover admin tool mode usability"
git push origin main
```
