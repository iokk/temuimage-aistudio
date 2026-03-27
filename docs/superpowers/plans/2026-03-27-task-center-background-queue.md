# Task Center Background Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified background task center so batch generation, quick generation, and image translation can run concurrently in the background while users switch between features and reopen historical task results.

**Architecture:** Generalize the existing image-translation background executor into a shared task-center layer, then attach `combo_generation`, `smart_generation`, and `image_translate` to it. Surface task presence through a global header indicator and a task-center panel that restores results back into the owning page state.

**Tech Stack:** Streamlit, Python, ThreadPoolExecutor, in-memory task registry, existing generation/translation flows.

---

### Task 1: Add failing tests for unified task-center metadata

**Files:**
- Create: `tests/test_task_center.py`
- Create: `temu_core/task_center.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from temu_core.task_center import build_task_badge, build_task_type_meta


class TaskCenterMetaTest(unittest.TestCase):
    def test_task_badge_shows_pending_count(self):
        badge = build_task_badge(2)
        self.assertTrue(badge["show"])
        self.assertIn("2", badge["label"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `".venv/bin/python" -m unittest tests/test_task_center.py`
Expected: FAIL because `temu_core.task_center` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `temu_core/task_center.py` with helpers for task badge metadata and task-type labels.

- [ ] **Step 4: Run test to verify it passes**

Run: `".venv/bin/python" -m unittest tests/test_task_center.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_task_center.py temu_core/task_center.py
git commit -m "test: add task center metadata helpers"
```

### Task 2: Extract a shared background-task registry

**Files:**
- Modify: `app.py`
- Modify: `temu_core/task_center.py`
- Extend: `tests/test_task_center.py`

- [ ] **Step 1: Add failing test for task filtering and restore routing**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement minimal shared registry helpers**
  - list tasks by owner
  - submit generic task
  - update task
  - remove finished task
  - define task types `combo_generation`, `smart_generation`, `image_translate`
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/task_center.py tests/test_task_center.py
git commit -m "feat: extract shared task center registry"
```

### Task 3: Move quick generation to background queue

**Files:**
- Modify: `app.py`
- Extend: `tests/test_task_center.py`

- [ ] **Step 1: Add failing test for smart task metadata and restore target**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement quick-generation task submission and restore path**
  - submit smart generation as background task
  - persist result payload into task record
  - allow reopening task into smart page results
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_task_center.py
git commit -m "feat: queue quick generation in task center"
```

### Task 4: Move batch generation to background queue

**Files:**
- Modify: `app.py`
- Extend: `tests/test_task_center.py`

- [ ] **Step 1: Add failing test for combo task metadata and restore target**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement batch-generation task submission and restore path**
  - submit combo generation as background task
  - persist result payload into task record
  - allow reopening task into combo page results
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_task_center.py
git commit -m "feat: queue batch generation in task center"
```

### Task 5: Migrate image translation onto the shared task center

**Files:**
- Modify: `app.py`
- Extend: `tests/test_task_center.py`

- [ ] **Step 1: Add failing test that image-translate tasks use shared task-center metadata**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement migration from dedicated translate task list to shared registry**
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_task_center.py
git commit -m "refactor: move image translate to shared task center"
```

### Task 6: Add global top-right task indicator and task-center panel

**Files:**
- Modify: `app.py`
- Modify: `temu_core/usability_ui.py`
- Extend: `tests/test_usability_ui.py`

- [ ] **Step 1: Add failing test for task indicator visibility and labels**
- [ ] **Step 2: Run tests to confirm failure**
- [ ] **Step 3: Implement header task indicator**
  - show pending count as a small dot / count in the top action area
  - open task-center panel
  - list recent tasks across 1/2/4
  - click task to restore corresponding page result
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

```bash
git add app.py temu_core/usability_ui.py tests/test_usability_ui.py
git commit -m "feat: add global task center indicator"
```

### Task 7: Verify end-to-end behavior

**Files:**
- None new

- [ ] **Step 1: Run unit tests**

Run: `".venv/bin/python" -m unittest discover -s tests`
Expected: PASS.

- [ ] **Step 2: Run syntax verification**

Run: `".venv/bin/python" -m py_compile app.py temu_core/task_center.py temu_core/usability_ui.py`
Expected: PASS.

- [ ] **Step 3: Run Streamlit health check**

Run headless server and verify `/_stcore/health` returns `ok`.

- [ ] **Step 4: Manual smoke expectations**
  - batch generation can be submitted to background
  - quick generation can be submitted to background
  - image translation still works in background
  - top-right task badge appears when tasks exist
  - clicking a task restores the correct page/result

- [ ] **Step 5: Commit and push**

```bash
git add .
git commit -m "feat: add unified background task center"
git push origin main
```
