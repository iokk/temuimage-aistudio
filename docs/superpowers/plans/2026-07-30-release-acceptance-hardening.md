# Release Acceptance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining task-security test gap, remove a current Streamlit compatibility warning, add a repeatable secret-safe provider acceptance command, and publish the exact verified release to CNB.

**Architecture:** Keep task execution behavior unchanged while strengthening its regression boundary. Treat provider acceptance as an operator-facing adapter over existing application APIs so credentials remain in the current Keychain/encrypted storage path. Replace deprecated Streamlit layout arguments mechanically and raise the declared Streamlit floor to the first locally verified compatible version.

**Tech Stack:** Python 3.9 and 3.12, `unittest`, Streamlit 1.50+, SQLite, Pillow, `urllib`, Git.

## Global Constraints

- The acceptance contract is `docs/superpowers/acceptance/2026-07-30-release-acceptance.md`; every acceptance ID in scope must have fresh evidence or an explicit environment gap.
- Work in the current dirty `main` checkout because the user explicitly requested completion and CNB publication of this accumulated project state.
- Preserve all existing user changes. Do not reset, checkout, force-push, rewrite history, or discard staged/unstaged files.
- Use strict red-green-refactor for production behavior changes. A test-only coverage improvement must receive an explicit mutation check proving that it catches the intended production regression.
- Never print, log, persist, stage, or commit provider secrets. Live checks may resolve the secret only inside the process making the request.
- Make exactly one paid live image request during final acceptance unless a failed request returns no billable image and a bounded retry is required to distinguish a transient upstream failure.
- Do not add product libraries. The official `httpx[socks]` transport extra may
  be declared if the supported Python 3.12 runtime proves that the existing
  system/manual SOCKS proxy feature cannot initialize without it.
- Do not add thread-killing code. Process-isolated provider workers remain a separate architecture project.
- A release cannot proceed with an open Critical or Important review finding.
- Push to CNB without `--force`; after push, `refs/heads/main` must equal the locally verified release commit.

---

### Task 1: Independently Cover Every Privileged Checkpoint Field

**Files:**
- Modify: `test_task_engine.py:112-141`

**Interfaces:**
- Consumes: `TaskExecution.checkpoint(**updates)` and module-level `TASK_CHECKPOINT_FIELDS`.
- Produces: one independent repository-mutation assertion per prohibited field.
- Prohibited representatives: `id`, `type`, `owner_id`, `status`, `claim_token`, `runner_id`, `available_at`, and `payload`.

- [ ] **Step 1: Replace the bundled privilege case with independent subtests**

Use a fresh spy and execution object for every field so rejection of one field cannot mask another:

```python
def test_checkpoint_rejects_each_privileged_field_before_repository_mutation(self):
    prohibited_updates = {
        "id": "other-id",
        "type": "other-type",
        "owner_id": "other-owner",
        "status": "done",
        "claim_token": "other-claim",
        "runner_id": "other-runner",
        "available_at": "2026-07-30T12:00:00+00:00",
        "payload": {"prompt": "mutated"},
    }
    for field, value in prohibited_updates.items():
        with self.subTest(field=field):
            repository = RepositorySpy()
            execution = TaskExecution(repository, claimed_task)
            with self.assertRaisesRegex(ValueError, field):
                execution.checkpoint(**{field: value})
            self.assertEqual(repository.updates, [])
```

- [ ] **Step 2: Run the independent-field test against current production code**

Run: `/usr/bin/python3 -m unittest -v test_task_engine.TaskEngineTests.test_checkpoint_rejects_each_privileged_field_before_repository_mutation`

Expected: PASS because the production allowlist was already fixed in the prior round. This is a test-coverage task, not a production behavior change.

- [ ] **Step 3: Prove the test catches an allowlist regression with a runtime mutation**

Run a one-off `unittest` runner that patches `task_engine.TASK_CHECKPOINT_FIELDS` to include `status`, then executes only the new test.

Expected: FAIL in the `status` subtest because `RepositorySpy.update()` is called. The mutation command must restore the constant automatically when its patch context exits; no source file changes are allowed.

- [ ] **Step 4: Re-run the unmutated task-engine suite**

Run: `/usr/bin/python3 -m unittest -v test_task_engine`

Expected: all task-engine tests pass.

- [ ] **Step 5: Record task evidence without committing yet**

Write the exact commands and pass/fail counts to this plan's SDD report. The release is committed only after all tasks and final review are complete.

---

### Task 2: Remove Streamlit's Deprecated Container-Width API

**Files:**
- Modify: `app.py` at every project-owned `use_container_width` call.
- Modify: `requirements.txt:1`
- Modify: `requirements-web.txt:1`
- Modify: `test_task_center.py:81-129`
- Create: `test_streamlit_compat.py`

**Interfaces:**
- Replaces: `use_container_width=True` with `width="stretch"` for Streamlit buttons, links, popovers, downloads, and images.
- Declares: `streamlit>=1.50.0` in both runtime requirement files.
- Preserves: visible control width and fixed image-grid layout.

- [ ] **Step 1: Write the failing renderer regression**

Change the existing task-result renderer assertion to require:

```python
streamlit.image.assert_called_once_with(
    "/tmp/one.png",
    caption="商品图 1",
    width="stretch",
)
```

- [ ] **Step 2: Write the failing compatibility guard**

Create an AST-based test that loads `app.py`, walks every `ast.Call`, and reports the line number for any keyword named `use_container_width`:

```python
def test_app_uses_supported_streamlit_width_keyword(self):
    tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    deprecated_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(keyword.arg == "use_container_width" for keyword in node.keywords)
    ]
    self.assertEqual(deprecated_lines, [])
```

- [ ] **Step 3: Run both tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_task_center.TaskCenterItemViewTests.test_renderer_uses_four_columns_and_full_width_images test_streamlit_compat`

Expected: renderer assertion reports the old keyword and the compatibility test reports all remaining source line numbers.

- [ ] **Step 4: Apply the mechanical production change**

Replace every `use_container_width=True` argument in `app.py` with `width="stretch"`. Do not change layout structure, button type, disabled state, keys, captions, or column counts. Raise both Streamlit minimum versions from `1.40.0` to `1.50.0`.

- [ ] **Step 5: Run targeted tests and confirm GREEN**

Run: `/usr/bin/python3 -m unittest -v test_task_center test_streamlit_compat`

Expected: all tests pass and the AST guard reports no deprecated keyword.

- [ ] **Step 6: Verify runtime compatibility on both installed interpreters**

Run:

```bash
/usr/bin/python3 -c 'import streamlit; assert tuple(map(int, streamlit.__version__.split(".")[:2])) >= (1, 50)'
/opt/homebrew/opt/python@3.12/libexec/bin/python3 -c 'import streamlit; assert tuple(map(int, streamlit.__version__.split(".")[:2])) >= (1, 50)'
```

Expected: exit 0 under Streamlit 1.50 and 1.60 respectively.

- [ ] **Step 7: Compile and run the affected UI smoke path**

Run: `PYTHONPYCACHEPREFIX=/tmp/tulite-pycache /usr/bin/python3 -m py_compile app.py`

Expected: exit 0. Browser verification is completed in Task 6 after service restart.

---

### Task 3: Add A Secret-Safe Provider Acceptance Command

**Files:**
- Create: `provider_acceptance.py`
- Create: `scripts/verify_provider.py`
- Create: `test_provider_acceptance.py`
- Modify: `README.md` in the local verification section.
- Modify: `DEPLOYMENT.md` in the deployment verification section.

**Interfaces:**
- Produces: `verify_provider(provider: dict, application, include_responses: bool = True, include_live_image: bool = False, image_output: Path | None = None) -> dict`.
- Produces: `redact_acceptance_error(message: str) -> str` that removes bearer tokens and `sk-`-style secrets in addition to application sanitization.
- Produces CLI: `python scripts/verify_provider.py [--provider-id ID] [--skip-responses] [--live-image --image-output PATH]`.
- Exit code: `0` only when every requested check passes; `1` for a completed report with failed checks; `2` for invalid CLI usage or missing provider.
- Output contract: JSON contains provider ID/name/type/base URL, check names, booleans, model counts, image dimensions/output path, and sanitized errors. It never contains `api_key`, Authorization headers, raw provider documents, or response bodies.

- [ ] **Step 1: Write failing secret-boundary tests**

Create fakes for model catalog, client text call, Responses call, and image generation. Assert the report contains no value equal to the fake secret and serialized JSON contains neither `Bearer` nor the fake `sk-...` value.

- [ ] **Step 2: Write failing capability-result tests**

Cover these literal outcomes:

```python
self.assertEqual(report["checks"]["models"]["count"], 2)
self.assertTrue(report["checks"]["models"]["configured_image_model_present"])
self.assertTrue(report["checks"]["text"]["ok"])
self.assertTrue(report["checks"]["responses"]["ok"])
self.assertEqual(report["checks"]["image"]["size"], [32, 32])
```

Add a failure fixture whose upstream message embeds a bearer token and HTML; assert only the bounded sanitized error remains.

- [ ] **Step 3: Run the new tests and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_provider_acceptance`

Expected: import failure because `provider_acceptance.py` does not exist.

- [ ] **Step 4: Implement the minimal verifier**

The verifier must:

1. Copy only safe provider metadata into the report.
2. Resolve the secret with `application.resolve_provider_api_key(provider)` and record only `configured: bool`.
3. Call `application.fetch_provider_models(provider)` and check the configured image model by ID.
4. Create the existing application client and call `test_connection()`.
5. For OpenAI providers when Responses is requested, call the existing raw `_openai_call("/responses", ...)` with the configured title model and a maximum of 16 output tokens; store only object/status/output-presence booleans.
6. Only when `include_live_image=True`, call `generate_image([], acceptance_prompt, "1:1", "1K", "high", "zh")`, verify dimensions and non-empty encoded bytes, and save to the explicit output path when provided.
7. Catch each boundary independently so one failed check does not erase the rest of the report.
8. Set top-level `ok` to `all(requested_check["ok"])`.

- [ ] **Step 5: Implement the thin CLI**

The script adds the repository root to `sys.path`, imports `app` and `verify_provider`, selects the explicit or active provider, runs the verifier, writes only JSON to stdout, and exits with the documented code. It must not accept an API key argument.

- [ ] **Step 6: Run targeted tests and confirm GREEN**

Run: `/usr/bin/python3 -m unittest -v test_provider_acceptance test_provider_models test_failed_item_retry`

Expected: all provider, model, timeout, retry, and verifier tests pass.

- [ ] **Step 7: Document safe usage**

Add the non-paid default command and the explicit paid image command to README and deployment verification. State that `--live-image` performs a billable request and that output must be outside the repository or under ignored `data/`.

- [ ] **Step 8: Run the non-paid live verifier**

Run: `/opt/homebrew/opt/python@3.12/libexec/bin/python3 scripts/verify_provider.py --provider-id ioio-gpt-image-2`

Expected: exit 0; model, text, and Responses checks pass; no key appears in stdout/stderr.

---

### Task 4: Package Every Local Runtime Module In Docker Images

**Files:**
- Create: `test_deployment_manifest.py`
- Modify: `Dockerfile`
- Modify: `Dockerfile.web`
- Modify: `DEPLOYMENT.md` provider-verification commands.

**Interfaces:**
- Both Dockerfiles must package `app.py`, `task_engine.py`, `task_store.py`, `task_status.py`, `run_tulite.py`, `provider_acceptance.py`, and `scripts/verify_provider.py`.
- The copied image filesystem must import the task modules and run `scripts/verify_provider.py --help` without resolving a local module from the repository checkout.
- Docker deployment verification runs inside the service container so it uses the saved container provider and mounted `data/` directory.

- [ ] **Step 1: Write the isolated Docker-copy regression**

Parse simple `COPY <source> <destination>` instructions with `shlex`, reproduce the copied Python files in a temporary directory, and run these subprocess checks with that directory as the working directory:

```python
subprocess.run(
    [sys.executable, "-c", "import app, task_engine, task_store, task_status, run_tulite"],
    cwd=image_root,
    capture_output=True,
    text=True,
)
subprocess.run(
    [sys.executable, "scripts/verify_provider.py", "--help"],
    cwd=image_root,
    capture_output=True,
    text=True,
)
```

Run the same behavior for `Dockerfile` and `Dockerfile.web`. The helper must copy only files explicitly named by each Dockerfile and must not add the repository to `PYTHONPATH`.

- [ ] **Step 2: Run the deployment test and confirm RED**

Run: `/usr/bin/python3 -m unittest -v test_deployment_manifest`

Expected: FAIL because neither Dockerfile copies `task_status.py`, `provider_acceptance.py`, or `scripts/verify_provider.py`; isolated `task_engine` import reports `ModuleNotFoundError: task_status`.

- [ ] **Step 3: Add the missing COPY instructions**

Add the three missing source artifacts to both Dockerfiles. Keep the base image, dependency install, environment, healthcheck, and entrypoint unchanged.

- [ ] **Step 4: Run the deployment test and confirm GREEN**

Run: `/usr/bin/python3 -m unittest -v test_deployment_manifest`

Expected: both isolated image-root import and CLI help checks pass.

- [ ] **Step 5: Correct Docker deployment verification commands**

In `DEPLOYMENT.md`, use:

```bash
docker compose exec workbench python scripts/verify_provider.py
docker compose exec workbench python scripts/verify_provider.py \
  --live-image \
  --image-output /app/data/provider-acceptance.png
```

- [ ] **Step 6: Record the Docker daemon environment gap**

Run `docker version`. If the daemon is unavailable, record the exact gap and rely on the isolated-copy regression plus Dockerfile review; do not claim a real image build occurred.

---

### Task 5: Execute One Real Image Task Through The Durable Engine

**Files:**
- Runtime evidence only: ignored `data/tasks.sqlite3`, ignored `data/files/` or a temporary output path.
- Modify after the run: `docs/superpowers/acceptance/2026-07-30-release-acceptance.md` final evidence section.

**Interfaces:**
- Consumes: active provider `ioio-gpt-image-2`, `create_task`, `TaskEngine`, `text_to_image` handler, and task store.
- Produces: one terminal task with exactly one decodable image and per-item result metadata.

- [ ] **Step 1: Snapshot runtime state without secrets**

Record the current task IDs/statuses, current provider ID, listener PID, and log offsets. Do not print provider JSON or key material.

- [ ] **Step 2: Run the paid provider check exactly once**

Run the provider verifier with `--live-image` and an ignored acceptance output path.

Expected: exit 0, `gpt-image-2` returns a decodable non-blank image, and the report includes dimensions but no response body or secret.

- [ ] **Step 3: Submit one durable text-to-image task**

Submit a deterministic acceptance prompt through `create_task("text_to_image", payload)` using the active provider. Record only the task ID. Do not call the image endpoint directly a second time for this step if Step 2 already produced the image; instead, when practical, make the durable task itself the single paid request and derive the provider image evidence from its terminal result.

- [ ] **Step 4: Observe the task without coupling to Streamlit reruns**

Poll the SQLite-backed store from a separate process until the task reaches `done`, `partial`, `error`, `cancelled`, or `expired`, with an upper bound of 360 seconds.

Expected: `done`; progress is `1/1`; one item is `done`; one result file exists and Pillow can decode it.

- [ ] **Step 5: Verify persistence and history**

Open a new store instance, read the same task ID, and confirm the terminal document and result file remain. Confirm history archival either succeeded or remains explicitly repairable without deleting the task.

- [ ] **Step 6: Review logs from the captured offset**

Expected: no new unhandled application traceback and no credential material. A transient upstream failure closes the release gate until its classification/recovery is verified and a bounded rerun decision is recorded.

- [ ] **Step 7: Clean acceptance-only artifacts**

Remove temporary output files that are not the retained live task result. Do not delete the accepted task or history record unless it is clearly labeled as an acceptance fixture and its durable evidence has been recorded.

---

### Task 6: Independent Review, Full Acceptance, And CNB Publication

**Files:**
- Review all files selected for the release commit.
- Modify: `docs/superpowers/acceptance/2026-07-30-release-acceptance.md` final sign-off.

**Interfaces:**
- Produces: zero open Critical/Important findings, fresh full-suite evidence, browser evidence, a secret-clean release commit, and matching local/CNB SHAs.

- [ ] **Step 1: Run per-task and whole-tree Superpowers reviews**

Review task privilege boundaries, provider secret handling, live-check cost boundaries, Streamlit compatibility, task durability, and release composition. Fix every Critical/Important finding through a focused failing test, then perform one scoped re-review.

- [ ] **Step 2: Run complete automated verification on Python 3.9**

Run:

```bash
/usr/bin/python3 -m unittest discover -v
PYTHONPYCACHEPREFIX=/tmp/tulite-pycache /usr/bin/python3 -m py_compile app.py provider_acceptance.py task_engine.py task_store.py task_status.py run_tulite.py scripts/verify_provider.py
```

Expected: zero failures and zero compile errors.

- [ ] **Step 3: Repeat the full suite on Python 3.12**

Run: `/opt/homebrew/opt/python@3.12/libexec/bin/python3 -m unittest discover -v`

Expected: zero failures and no Python end-of-life warning.

- [ ] **Step 4: Run static and secret checks**

Run `git diff --check`, an AST/dependency compile check, and a secret scan over tracked files plus the staged diff. Explicitly scan for the known supplied key fingerprints without printing matches.

Expected: zero whitespace errors, zero syntax errors, zero secret matches.

- [ ] **Step 5: Restart the local service on supported Python and verify one instance**

Restart `com.tulite.local` using the locally installed supported Python 3.12 interpreter, poll `/_stcore/health`, and inspect listeners.

Expected: HTTP 200 and exactly one process listening on `127.0.0.1:8501`.

- [ ] **Step 6: Perform desktop and mobile browser acceptance**

At 1440px and 390px widths verify provider selection, task center, active progress, recent result thumbnails, state actions, no horizontal overflow, and no project-owned deprecation error in the page/log.

- [ ] **Step 7: Finalize acceptance evidence**

Update every pending sign-off field with commands, counts, live check results, review disposition, residual risk, and the planned release commit message. No API key or raw upstream body may be copied into the document.

- [ ] **Step 8: Fetch and reconcile CNB without rewriting history**

Fetch `cnb/main`, inspect the merge base and commits unique to each side, and integrate remote work with a normal merge or fast-forward. If conflicts occur, preserve both current project behavior and remote-only changes, then re-run Steps 2-6 on the reconciled tree.

- [ ] **Step 9: Stage the reviewed release set and scan it again**

Review `git status`, `git diff --cached --stat`, and `git diff --cached --name-status`. Stage the complete intended project while leaving ignored runtime data out. Re-run the known-key and generic-secret scan over `git diff --cached`.

- [ ] **Step 10: Commit and push CNB main without force**

Commit with a release-oriented message, push `main` to `cnb`, then query `refs/heads/main`.

Expected: local `HEAD` equals CNB `main`. If the remote advances between fetch and push, fetch and reconcile again; never force-push.

- [ ] **Step 11: Post-push verification**

Recheck local health, current provider ID, task count/status summary, clean staged state, and CNB SHA. Record the final evidence in the acceptance document.
