# Task System Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent task-record loss and lifecycle corruption, make delayed scheduling timezone-safe, and expose compact per-item task results without reintroducing page-refresh coupling.

**Architecture:** Put task lifecycle vocabulary in one dependency-free domain module, keep SQLite responsible for durable queue and retention rules, and keep `TaskExecution` as a narrow checkpoint capability. Build a pure task-item view model before rendering it with Streamlit so state semantics are unit-testable and the UI can use a stable four-column thumbnail grid.

**Tech Stack:** Python 3.9, `unittest`, SQLite, Streamlit, Pillow.

## Global Constraints

- Preserve all pre-existing staged and unstaged user changes; do not reset, stage, unstage, commit, or rewrite unrelated files.
- Use strict red-green-refactor: every production behavior change must first have a focused test that fails for the expected reason.
- Add no dependencies and preserve the existing SQLite schema and task document format.
- Preserve single-installation owner scoping and the current manual retry policy.
- Never delete an unarchived terminal task to make queue capacity available.
- The project-center action labeled “清理已完成项目” may delete only `done` task rows.
- Task handlers may checkpoint progress/result data but may not mutate identity, ownership, claim, scheduling, or lifecycle fields.
- A delayed task must be compared as an absolute instant when an offset is supplied; naive timestamps remain interpreted in the machine’s local timezone for backward compatibility.
- A single successful image must remain a thumbnail-sized result in a fixed four-column grid rather than expanding across the page.
- Do not add a thread-killing watchdog. A safe hard timeout requires process-isolated workers and is outside this repair.

---

### Task 1: Centralize Lifecycle Status And Protect Repairable Records

**Files:**
- Create: `task_status.py`
- Modify: `task_store.py:15-21,121-149,515-519`
- Modify: `task_engine.py:13-16`
- Modify: `app.py:31-32,182,2239,2491-2494,2816-2821,2845,2895-2903,2987,7436,7962`
- Test: `test_task_store.py:65-104`
- Test: `test_task_scheduler.py:280-399`

**Interfaces:**
- Produces: `TASK_TERMINAL_STATUSES: frozenset[str]`, `TASK_COMPLETED_STATUSES: frozenset[str]`, and `TASK_STATUS_TRANSITIONS: Mapping[str, frozenset[str]]` from `task_status.py`.
- Preserves: `SqliteTaskStore.create(task, max_tasks, terminal_statuses)` compatibility while using the passed/shared terminal vocabulary.
- Produces: `clear_completed_tasks() -> int`; removes the misleading `clear_terminal_tasks()` UI seam.

- [ ] **Step 1: Write the capacity-retention regression tests**

Add tests proving an archived terminal row is prunable and an unarchived terminal row causes `TaskCapacityError` while remaining readable:

```python
def test_capacity_prunes_oldest_archived_terminal_task_before_creating(self):
    archived = make_task("archived", status="done", history_archived_at="2026-07-29T09:30:00")
    store.create(archived, 1, TERMINAL_STATUSES)
    store.create(make_task("replacement", created_at="2026-07-29T11:00:00"), 1, TERMINAL_STATUSES)
    self.assertIsNone(store.get("archived"))

def test_capacity_never_prunes_unarchived_terminal_task(self):
    pending_archive = make_task("pending-archive", status="error")
    store.create(pending_archive, 1, TERMINAL_STATUSES)
    with self.assertRaises(TaskCapacityError):
        store.create(make_task("replacement"), 1, TERMINAL_STATUSES)
    self.assertEqual(store.get("pending-archive"), pending_archive)
```

- [ ] **Step 2: Run the two capacity tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_store.SqliteTaskStoreTests.test_capacity_prunes_oldest_archived_terminal_task_before_creating test_task_store.SqliteTaskStoreTests.test_capacity_never_prunes_unarchived_terminal_task`

Expected: the archived fixture setup or old pruning expectation fails until the fixture/test helper supports `history_archived_at`, and the unarchived task is incorrectly deleted.

- [ ] **Step 3: Write application cleanup regressions**

Add tests using a temporary real `SqliteTaskStore` to prove `clear_completed_tasks()` removes `done` but preserves `partial/error/cancelled/expired`, plus a patched history-data test proving `purge_all_trashed_history_records()` removes a trashed `partial` record.

- [ ] **Step 4: Run the cleanup tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_scheduler.TaskHistoryArchivingTests.test_clear_completed_tasks_preserves_non_done_terminal_rows test_task_scheduler.TaskHistoryArchivingTests.test_purge_all_trash_includes_partial_results`

Expected: the current cleanup deletes all terminal task rows and the current purge leaves the `partial` history row behind.

- [ ] **Step 5: Implement the shared lifecycle policy and minimal retention fixes**

Create the dependency-free status module, import it from store/engine/app, require truthy `history_archived_at` when selecting a capacity victim, rename the application cleanup seam to `clear_completed_tasks`, and use the shared terminal set for full trash purge.

- [ ] **Step 6: Run targeted and affected tests; record the diff without committing**

Run: `/usr/bin/python3 -m unittest -v test_task_store test_task_scheduler`

Expected: all task-store and scheduler/history tests pass.

---

### Task 2: Restrict Checkpoints To Recoverable Execution Data

**Files:**
- Modify: `task_engine.py:75-95`
- Test: `test_task_engine.py:71-99`

**Interfaces:**
- Produces: `TaskExecution.checkpoint(**updates) -> dict` accepting only `progress`, `result_files`, `item_results`, and `errors`.
- Raises: `ValueError` listing unsupported fields before any repository mutation.
- Preserves: claim-token and `running` preconditions for allowed checkpoints.

- [ ] **Step 1: Write the lifecycle-corruption regression test**

```python
def test_checkpoint_rejects_lifecycle_and_identity_fields(self):
    self.enqueue(make_task("guarded-checkpoint"))
    claimed = self.repository.claim_next(1, "test-runner")
    execution = TaskExecution(self.repository, claimed)
    with self.assertRaisesRegex(ValueError, "status.*owner_id"):
        execution.checkpoint(status="done", owner_id="other-workspace")
    persisted = self.repository.get("guarded-checkpoint")
    self.assertEqual(persisted["status"], "running")
    self.assertEqual(persisted["owner_id"], "test-workspace")
```

- [ ] **Step 2: Run the checkpoint test and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_engine.TaskEngineTests.test_checkpoint_rejects_lifecycle_and_identity_fields`

Expected: no `ValueError`; the persisted task is mutated.

- [ ] **Step 3: Implement a checkpoint field allowlist**

Validate all keys before adding the internal `updated_at`. Keep the allowlist next to `TaskExecution` and raise before calling `repository.update`.

- [ ] **Step 4: Run targeted and affected tests; record the diff without committing**

Run: `/usr/bin/python3 -m unittest -v test_task_engine test_task_scheduler`

Expected: normal progress/result checkpoints still pass and forbidden mutations are rejected.

---

### Task 3: Compare Delayed Tasks As Absolute Instants

**Files:**
- Modify: `task_store.py:10,192-221,349-423,483-498`
- Test: `test_task_store.py:239-270,529-566`

**Interfaces:**
- Produces: internal `_normalize_available_at(value) -> str`, returning an empty string or a fixed-width UTC ISO timestamp.
- Treats: offset-aware strings as absolute instants and naive strings/datetimes as local wall time for backward compatibility.
- Rejects: a newly persisted non-empty invalid timestamp with `ValueError`.
- Migrates: existing valid `available_at` index values idempotently during store initialization; malformed legacy values become non-claimable rather than immediately runnable.

- [ ] **Step 1: Write the offset scheduling regression test**

```python
def test_claim_next_compares_available_at_as_an_absolute_instant(self):
    future = make_task("future-offset", available_at="2026-07-29T04:30:00+00:00")
    store.create(future, 10, TERMINAL_STATUSES)
    now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    self.assertIsNone(store.claim_next(1, "timezone-runner", now=now))
```

Also add a test that a malformed non-empty `available_at` is rejected on create and not persisted.

- [ ] **Step 2: Run the timezone tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_store.SqliteTaskStoreTests.test_claim_next_compares_available_at_as_an_absolute_instant test_task_store.SqliteTaskStoreTests.test_create_rejects_invalid_available_at`

Expected: the future task is claimed early and malformed text is accepted.

- [ ] **Step 3: Normalize SQLite scheduling keys to UTC**

Normalize both the stored `available_at` column and the claim comparison timestamp to UTC. Keep the task JSON contract intact, and run an idempotent column repair after schema migration for existing rows.

- [ ] **Step 4: Run targeted and store tests; record the diff without committing**

Run: `/usr/bin/python3 -m unittest -v test_task_store`

Expected: priority/FIFO behavior remains intact and timezone-aware delayed work is not claimed early.

---

### Task 4: Expose Compact Per-Item Results In Task Center

**Files:**
- Modify: `app.py:7415-7518`
- Create: `test_task_center.py`

**Interfaces:**
- Produces: `build_task_item_views(task: dict) -> list[dict]` with stable `index`, `label`, `status`, `file_path`, and `error` fields.
- Preserves: legacy tasks that have `result_files` but no `item_results` by synthesizing successful display items.
- Produces: `render_task_item_results(task, show_images: bool)` using a fixed four-column grid for successful files and compact text for pending/error states.

- [ ] **Step 1: Write pure view-model regressions**

Add a mixed-result test with out-of-order item indexes and `progress.total == 3`; assert the returned views are ordered `1..3`, preserve the successful file, preserve the failed error, and synthesize one `pending` item. Add a legacy-result test proving `result_files` remain visible when `item_results` is absent.

- [ ] **Step 2: Run the task-center tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_center`

Expected: import failure because the pure view-model function does not exist.

- [ ] **Step 3: Implement the pure view model and compact renderer**

In active tasks, retain the single progress bar and add only a compact per-item state caption when checkpoints exist. In recent tasks, wrap each task once, show its summary/error/retry action, and render successful images through four fixed columns so one image occupies one column instead of the full content width.

- [ ] **Step 4: Run targeted tests and syntax checks; record the diff without committing**

Run: `/usr/bin/python3 -m unittest -v test_task_center test_task_scheduler test_failed_item_retry`

Run: `PYTHONPYCACHEPREFIX=/tmp/tulite-pycache /usr/bin/python3 -m py_compile app.py task_engine.py task_store.py task_status.py`

Expected: all targeted tests and compilation pass.

---

### Task 5: Independent Review, Full Verification, And Local UI Smoke Test

**Files:**
- Review only: `task_status.py`, `task_store.py`, `task_engine.py`, `app.py`, `test_task_store.py`, `test_task_engine.py`, `test_task_scheduler.py`, `test_task_center.py`

**Interfaces:**
- Consumes: all behavior delivered by Tasks 1-4.
- Produces: review findings, fresh verification evidence, and a running local deployment at `http://127.0.0.1:8501/`.

- [ ] **Step 1: Request an independent code review**

Review for data loss, transaction safety, timezone correctness, checkpoint privilege escalation, UI state clarity, image sizing, and missing regression coverage. Fix Critical/Important findings through another red-green cycle and re-review the fix diff.

- [ ] **Step 2: Run the complete automated verification**

Run: `/usr/bin/python3 -m unittest discover -v`

Run: `PYTHONPYCACHEPREFIX=/tmp/tulite-pycache /usr/bin/python3 -m py_compile app.py task_engine.py task_store.py task_status.py run_tulite.py`

Run: `git diff --check`

Expected: zero failures, zero compile errors, and zero whitespace errors.

- [ ] **Step 3: Restart the local service and verify health**

Restart `com.tulite.local`, then verify `http://127.0.0.1:8501/_stcore/health` returns HTTP 200. Do not leave a duplicate development server running.

- [ ] **Step 4: Perform browser smoke testing**

Open the task center, verify queued tasks show one stable progress presentation, recent mixed tasks show per-item states, successful images appear in a four-column thumbnail grid, retry remains limited to failed smart-task items, and no UI element overlaps at desktop width.

- [ ] **Step 5: Report evidence and remaining architecture risk**

Report changed files and verification output. Keep the known task-thread watchdog limitation explicit: process isolation remains the correct future boundary for safely terminating permanently stuck provider calls.
