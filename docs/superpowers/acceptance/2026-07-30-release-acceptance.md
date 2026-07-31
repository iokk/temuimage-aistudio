# TuLite V15.2.1 Release Acceptance

**Date:** 2026-07-30 through 2026-07-31
**Target:** local single-user deployment and CNB `main` release
**Repository:** `imqie/tulite`
**Acceptance owner:** test engineering
**Status:** reference-image recovery accepted locally; final verification passed; release change set committed locally

## 1. Acceptance Goal

This release is accepted only when the current local application can be started, used, stopped, and restarted without losing task truth; the configured provider account can complete model, text, and image checks; task-center behavior remains stable without depending on page refreshes; no tracked secret or local runtime data is present; and the exact verified tree is pushed to the CNB repository.

"No systemic risk" means there is no known Critical or Important defect in the tested scope below. It does not mean an absolute guarantee against upstream provider outages, operating-system failures, or untested future dependency versions. Any remaining Minor or external risk must have an owner-visible recovery path and cannot invalidate stored task or account data.

## 2. Scope

### In scope

- Local Streamlit startup, health, restart, and single-instance behavior.
- Provider creation, secret resolution, active-provider selection, model catalog, and connection checks.
- The configured `ioio GPT Image 2` account at `https://ioio.nowdn.com/v1`.
- OpenAI-compatible `/models`, `/chat/completions`, `/responses`, and `/images/generations` behavior needed by this installation.
- Text-to-image submission through the durable background task engine.
- Reference-image submission through quick generation, translation, smart generation, and combo generation.
- Reference-image upload persistence, task-payload durability, worker-side loading, provider request encoding, retry, and sanitized diagnostics.
- Task visibility, lifecycle transitions, checkpoints, cancellation, retention, retry eligibility, and result rendering.
- Desktop and mobile task-center rendering, including compact image results.
- Automated unit/integration tests, compilation, dependency/runtime smoke checks, and log review.
- Secret scanning, release commit composition, CNB synchronization, and post-push verification.

### Out of scope

- Guaranteed availability or latency of the third-party upstream.
- Multi-host scheduling and distributed database deployment.
- Forced termination of arbitrary Python threads. Local recovery is service restart; a future hard-kill design requires process-isolated provider workers.
- Destructive load tests or repeated paid image generation. Live acceptance uses one smallest practical image generation.

## 3. Risk Severity And Release Gate

| Severity | Definition | Release rule |
| --- | --- | --- |
| Critical | Secret exposure, unrecoverable data loss, arbitrary cross-owner mutation, or unusable application | Must be fixed and independently re-reviewed |
| Important | Core workflow failure, task disappearance, false success, unbounded queue corruption, or repeatable provider incompatibility | Must be fixed and independently re-reviewed |
| Minor | Non-blocking maintainability, warning, narrow test granularity, or documented local recovery limitation | Fix when low risk; otherwise document with recovery |
| External | Upstream availability, quota, moderation, rate limiting, or network behavior outside this repository | Must be correctly classified, sanitized, and recoverable |

The release gate is closed while any Critical or Important finding remains open.

## 4. Acceptance Matrix

### A. Repository And Security

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| SEC-01 | API keys never enter tracked files, logs selected for commit, test fixtures, or documentation | Scan tracked content and staged diff for key/token patterns and known supplied values | Zero matches outside explicit placeholders |
| SEC-02 | Local account data remains ignored | Inspect `.gitignore`, Git index, and release file list | `data/`, `.env`, SQLite/WAL/SHM, provider JSON, uploads, and logs are absent |
| SEC-03 | Provider errors do not echo credentials or upstream HTML | Unit tests for sanitization plus live failure-message review | User-visible errors are bounded, readable, and secret-free |
| SEC-04 | Release history is non-destructive | Compare local, `origin/main`, and `cnb/main`; push without force | No force push, reset, or unrelated-history deletion |

### B. Provider And Account

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| API-01 | Active provider is unambiguous and persistent | Read provider metadata, restart service, re-read active provider | Same enabled provider remains current |
| API-02 | Stored secret resolves without being printed | Application secret resolver with boolean-only output | `has_api_key=true`; no secret appears in output |
| API-03 | Model catalog is reachable | Live `GET /v1/models` through application code | HTTP success, non-empty catalog, `gpt-image-2` present |
| API-04 | OpenAI-compatible text call works | One minimal `Return exactly OK` call | Non-empty response, no retry exhaustion |
| API-05 | Responses API works for the configured account | One minimal `/v1/responses` call | Response object completes and contains output |
| API-06 | Image model is genuinely usable | One `1024x1024`, medium-quality `/v1/images/generations` request | A decodable, non-blank image is returned |
| API-07 | Routine connection test does not claim image success without evidence | Review UI wording and structured test evidence | Text/model checks and paid image check are reported separately |
| API-08 | Upstream transient failures are recoverable | Unit tests plus log classification for 429/502/503/504/timeout | Retry metadata is set, successful items are preserved, secrets/HTML are hidden |

### C. Task Engine And Persistence

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| TASK-01 | Submission is durable before success is shown | Temporary SQLite integration test and live task submission | Task is readable after a new store instance opens |
| TASK-02 | Work continues without a Streamlit page rerun | Engine integration test and live page navigation during work | Task reaches a terminal state while another page is open |
| TASK-03 | Submitted tasks remain discoverable | Submit, navigate away, open task center, restart, open task center again | Same task ID remains visible throughout |
| TASK-04 | Lifecycle mutations are claim- and state-guarded | Store/engine tests | Late workers cannot overwrite cancellation or terminal state |
| TASK-05 | Checkpoints cannot mutate privileged fields | Independent cases for lifecycle, identity, ownership, claim, runner, scheduling, type, and payload fields | Every field is rejected before repository mutation |
| TASK-06 | Scheduling compares absolute instants correctly | UTC/offset/legacy migration tests | Future work is never claimed early; malformed legacy values are quarantined |
| TASK-07 | Capacity cannot delete repairable work | Capacity transaction tests | Only archived terminal rows can be pruned; rollback restores victims |
| TASK-08 | Partial results survive failure or interruption | Smart/combo/translate checkpoint recovery tests | Completed files and per-item states remain readable |
| TASK-09 | Retry never reruns successful images | Failed-item retry tests | Only retryable failed smart-task items enter the child task |
| TASK-10 | One user submission creates one durable task | UI payload review and live smoke test | User is not required to submit once per output item |

### D. Reference-Image Workflow

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| REF-01 | Uploaded reference images are persisted before task submission | Unit/integration test around upload persistence and task creation | Task payload contains durable application-owned paths, not transient upload/session objects |
| REF-02 | Persisted reference paths survive page reruns and service restart | Submit a task, reopen it through a new store/application instance, and inspect every referenced file | Every path remains readable, non-empty, and decodable after restart |
| REF-03 | Every reference-image task type loads the intended images | Focused handler tests for quick generation, translation, smart generation, combo generation, and failed-item retry | Loaded image count and order match the submitted payload; missing/corrupt paths fail explicitly before a provider call |
| REF-04 | OpenAI-compatible image edits use the provider contract required by the configured account | Request-boundary regression test plus one live reference-image request | The request contains the configured model, prompt, supported size/quality, and every reference image in the provider-accepted multipart shape |
| REF-05 | Reference-image failures identify the broken boundary | Inject local-file, encoding, HTTP, timeout, and malformed-response failures | User-visible errors distinguish local reference loading/request construction from upstream connectivity while remaining secret-free |
| REF-06 | Retry preserves reference-image inputs without rerunning successful items | Failed-item retry regression and persisted child-task inspection | Child payload retains valid durable image paths and includes only retryable failed items |
| REF-07 | A real reference-image task completes end to end | Submit one smallest practical quick-generation task using the latest failed task's retained reference image | Task reaches `done` or `partial` with one decodable non-blank output and no new unhandled traceback |

### E. User Interface

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| UI-01 | Active task presentation is stable | Desktop browser inspection while queued/running | One progress presentation; no duplicate status blocks or incoherent refresh artifacts |
| UI-02 | Recent image results remain compact | Desktop browser inspection with one and multiple results | Four-column task-result grid; one image does not fill the viewport |
| UI-03 | Mobile layout has no horizontal overflow | 390px browser inspection | `scrollWidth <= clientWidth`; text and controls remain readable |
| UI-04 | Provider selection is immediately understandable | Provider-page browser inspection | Current provider is visually named first and selector state matches it |
| UI-05 | Streamlit API use is supported by the declared minimum version | Warning scan and compatibility tests | No project-owned deprecated `use_container_width` calls remain |
| UI-06 | Empty, queued, running, partial, failed, cancelled, expired, and done states are coherent | View-model tests and browser fixtures/live task | Every state has one clear summary and valid actions only |

### F. Runtime And Release

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| RUN-01 | Full automated suite passes | `/usr/bin/python3 -m unittest discover -v` and Python 3.12 repeat | Zero failures or errors |
| RUN-02 | Source compiles | `py_compile` for launch and task modules on supported Python | Exit 0 |
| RUN-03 | Service health is reliable | Restart local service, poll health endpoint | HTTP 200 with one listener on port 8501 |
| RUN-04 | Logs contain no new unhandled application error | Review logs after acceptance flow | No new traceback outside deliberately injected test failures |
| RUN-05 | Container definition builds from complete source set | Static Dockerfile check and build when local Docker is available | All imported local modules are copied; build exits 0 or an explicit environment gap is recorded |
| REL-01 | Release commit contains the intended project and acceptance evidence | Review staged file list and diff statistics | No runtime data/secret; no missing task modules/tests/docs |
| REL-02 | Exact verified commit reaches CNB | Non-force push, then `git ls-remote` | CNB `refs/heads/main` equals local release commit |
| REL-03 | Post-push local health remains green | Health check after push | HTTP 200 and active provider/task data unchanged |

## 5. Required Test Order

1. Capture the current green baseline and runtime metadata.
2. Write acceptance documentation before production edits.
3. For each behavior change, add one focused failing regression and record the expected failure.
4. Implement only enough to make that regression pass.
5. Run the affected tests, then the complete suite.
6. Perform an independent task review and a final whole-tree review.
7. Run live model/text/Responses checks, then exactly one live image request.
8. Re-run the latest failed reference-image fixture through the provider request boundary, then submit one real reference-image task through the durable engine and observe it to terminal state.
9. Submit a real text-to-image control task only when needed to distinguish a provider-wide outage from an image-edit incompatibility.
10. Inspect desktop and mobile UI, service health, and logs.
11. Delete or clearly label acceptance fixtures, scan secrets, commit, push without force, and verify the remote SHA.

## 6. Baseline Evidence

Captured before this acceptance round changes production code:

- Branch: `main`; local branch initially one commit ahead of `origin/main`.
- Local service: one listener at `127.0.0.1:8501`; health returned HTTP 200.
- Automated suite: 73 tests passed under Apple system Python 3.9.
- Active account: `ioio GPT Image 2`; key resolved from Keychain without being printed.
- Model catalog: 20 entries; `gpt-image-2` present.
- Minimal Chat Completions call: passed.
- Minimal Responses call: passed with `status=completed` and non-empty output.
- Existing provider failure logs: transient upstream timeout/502/503/504 classification, not authentication failure.
- Baseline warnings: Python 3.9/Google-auth end-of-life warning and Streamlit `use_container_width` deprecation warning.
- Browser reproduction at `2026-07-30T20:36:18.873269`: the latest quick-generation task used one reference image and failed with the generic message `提供商连接失败，请检查 Base URL、代理或网络。`
- Control case at `2026-07-30T12:14:15.709402`: the same configured provider completed the release-acceptance text-to-image task successfully.
- Initial classification: the reference-image/image-edit path was an open Important defect. REF-01 through REF-07 now have fresh local evidence in Section 9.

## 7. Acceptance-Round Changes

- Reproduced the latest reference-image failure from persisted task `aaea6a8f65ed` and reused its durable input path.
- Added failing regressions for sanitized connection retry eligibility, migration of pre-fix failed items, missing reference inputs, and repeated retry-summary prefixes.
- Replaced silent reference-image load fallback with a bounded explicit error that identifies only the input filename.
- Classified provider connection failures as transient, retained cooldown metadata, and migrated historical records without adding automatic paid-request retries.
- Preserved failed-item-only retry behavior and durable reference-image paths.
- Normalized retry summaries at task creation and display time without rewriting historical records.
- Re-ran the real reference-image task to completion and updated this document with fresh evidence and residual risks.

## 8. Systematic Review And Cleanup Plan

The cleanup pass is constrained to behavior exposed by the reference-image failure:

1. Lock the latest sanitized connection failure with a regression test proving it remains eligible for failed-item-only retry after the cooldown.
2. Lock missing and corrupt reference inputs with regression tests proving the provider is never called after a local load failure.
3. Replace broad fallback behavior only at the reference-image boundary; preserve the existing durable task and paid-request semantics.
4. Keep multipart construction and immediate-retry behavior unchanged unless a boundary test or live probe proves incompatibility.
5. Run focused tests after each change, then the complete suite, compilation, browser acceptance, and log review.

Fallback inventory:

- `load_image_paths()` catches every exception and silently drops the failed path. Classification: masking fallback; remove and replace with a bounded reference-input error.
- `classify_image_task_error()` treats sanitized connection failures as permanent. Classification: behavior gap; add explicit transient connection metadata without automatic paid retries.
- OpenAI image-edit calls use one immediate attempt. Classification: intentional billing-safety policy; preserve.
- Failed-item retry reuses durable `image_paths` and skips completed items. Classification: intentional recovery path; preserve and re-verify.

## 9. Final Evidence

### Root-cause conclusion

- The retained reference file `data/task_uploads/smart_1785414942_1.png` was present, non-empty, and decodable as a `1200x1200` RGB PNG.
- A controlled image-edit request using the same file succeeded in `48.1` seconds. The exact persisted `705`-character task prompt also succeeded in `48.1` seconds. This rules out a stable file-format, multipart-shape, model, or prompt incompatibility.
- Two retries inside the original long-lived service process, `37bcbe2b3399` and `fd79e1f84792`, failed after approximately `61` seconds with upstream timeout behavior.
- After a clean local service restart, the same durable task input and prompt completed through the background task engine. The observed trigger was therefore an intermittent upstream/runtime connection state, not an unusable reference image.
- The application defect was recoverability: sanitized connection failures were stored as permanent, historical failures could not be retried, and unreadable local reference paths were silently discarded.

### Reference-image acceptance

- Successful task: `f18a038265f0`.
- Created: `2026-07-30T23:04:13.164387`.
- Started: `2026-07-30T23:04:15.017108`.
- Completed: `2026-07-30T23:05:14.221349`.
- Result: `done`, success `1`, failed `0`, no stored errors.
- Output: `data/task_results/f18a038265f0_01_卖点图.png`.
- Output validation: decodable non-blank RGB PNG, `1254x1254`, `1,642,210` bytes, with full-channel extrema `0..255`.
- Browser validation: desktop task center displayed the task as completed with one visible result. At a `390x844` viewport, `scrollWidth == clientWidth == 390`; the result rendered at `315x315` with natural width `1254`.
- Historical connection and timeout failures now expose failed-item-only retry after cooldown. Repeated retry prefixes display as one normalized prefix.

### Reference-image batch retest and recovery

- Input: persisted USB-C multiport-hub reference image; selected `Main Image on White` and `Feature Highlight` for one two-image combo task.
- First live combo task: `244176a9cb70` reached `partial`; it retained the successful `Main Image on White` output at `data/task_results/244176a9cb70_01_Main Image on White.png`. The output is a decodable `1254x1254` RGB PNG. The `Feature Highlight` provider call timed out.
- Repeated failed-item-only live retries reproduced the same upstream timeout. The final retry task `406e44a6bf31` submitted only the retained failed request, with original batch index `2`, and reached `partial` rather than terminal `error`.
- Stored result evidence for `406e44a6bf31`: one failed `Feature Highlight` item, `upstream_timeout`, `retryable=true`, a cooldown deadline, preserved reference-image request data, and no completed output was discarded.
- Browser review exposed a second local defect: an original batch index of `2` caused a one-item retry task to render an invented `第 1 项` alongside `Feature Highlight`; its summary also retained the parent task's `2张` label.
- The follow-up TDD repair keeps the original batch index for file naming and retry recovery, compacts only the display indexes for a retry child, and derives the displayed count from the child task's actual total. New retry submissions now store `重试失败项 · 智能组图任务 · 1张`.
- Final browser verification shows task `406e44a6bf31` as `部分完成 · 重试失败项 · 智能组图任务 · 1张`, with success `0`, failure `1`, exactly one `Feature Highlight` failure row, and one `重试失败项 (1)` action.

### Automated and runtime acceptance

- Focused reference/retry/task-center suite: `41` tests passed.
- Python 3.12 full suite: `138` tests passed.
- Apple system Python 3.9 compatibility suite: `138` tests passed; the existing Google-auth Python 3.9 end-of-life warning remains.
- `py_compile` passed for the application, task engine/store/status, launcher, and image-edit diagnostic modules.
- `git diff --check` passed.
- Runtime-data inspection found no tracked `data/`, `.env`, SQLite, upload, result, or log files; the paths are covered by `.gitignore`.
- The service has one listener on `127.0.0.1:8501` and `/_stcore/health` returns `ok`.
- No failure was logged for successful task `f18a038265f0`. Later `translate-checkpoint` error lines were deliberately injected by passing recovery tests.

## 10. Residual-Risk Policy

The following may remain only if final review confirms they are not Critical or Important:

- A provider call that defeats socket timeouts can keep one thread occupied until service restart. The task database remains durable and a second worker remains available; restart is the documented local recovery. Process isolation is the future hard-termination boundary.
- Third-party 429/5xx/timeout behavior may still occur. The application must preserve successes, classify the failed item, enforce cooldown, and permit failed-item-only retry where supported.
- Python 3.9 can remain a compatibility test interpreter, but the release runtime must also pass on an actively supported Python version.
- The configured upstream image provider can still time out on individual reference-image variants. The application preserves successful outputs, records the failed item with retry metadata, and exposes failed-item-only retry without rerunning successful images.

## 11. Final Sign-Off

This section is completed only after fresh verification:

- Focused reference/retry/task-center suite: `41` tests passed.
- Automated tests: passed, `138/138` on Python 3.12 and `138/138` on Python 3.9.
- Live provider checks: passed for the existing model/text/Responses baseline and two controlled reference-image edit probes.
- Live image task: passed.
- Live reference-image task: passed as `f18a038265f0`.
- Desktop/mobile browser acceptance: passed for the task-center reference-image result and horizontal-overflow check.
- Security scan: passed for the changed tree and ignored local runtime paths; no credential value was found.
- Final Superpowers review: passed for the local reference-image scope.
- Release commit: local commit requested; final SHA recorded in the local Git log.
- CNB `main` SHA: not updated; not requested in this task.
- Open Critical findings in the tested local scope: `0`.
- Open Important findings in the tested local scope: `0`.
- Residual Minor/external risks: upstream timeout/connection recurrence and the Python 3.9 end-of-life warning, both with documented recovery or compatibility evidence.
