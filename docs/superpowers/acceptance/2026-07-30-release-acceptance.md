# TuLite V15.2.1 Release Acceptance

**Date:** 2026-07-30
**Target:** local single-user deployment and CNB `main` release
**Repository:** `imqie/tulite`
**Acceptance owner:** test engineering
**Status:** in progress

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

### D. User Interface

| ID | Requirement | Verification | Pass condition |
| --- | --- | --- | --- |
| UI-01 | Active task presentation is stable | Desktop browser inspection while queued/running | One progress presentation; no duplicate status blocks or incoherent refresh artifacts |
| UI-02 | Recent image results remain compact | Desktop browser inspection with one and multiple results | Four-column task-result grid; one image does not fill the viewport |
| UI-03 | Mobile layout has no horizontal overflow | 390px browser inspection | `scrollWidth <= clientWidth`; text and controls remain readable |
| UI-04 | Provider selection is immediately understandable | Provider-page browser inspection | Current provider is visually named first and selector state matches it |
| UI-05 | Streamlit API use is supported by the declared minimum version | Warning scan and compatibility tests | No project-owned deprecated `use_container_width` calls remain |
| UI-06 | Empty, queued, running, partial, failed, cancelled, expired, and done states are coherent | View-model tests and browser fixtures/live task | Every state has one clear summary and valid actions only |

### E. Runtime And Release

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
8. Submit a real text-to-image task through the durable engine and observe it to terminal state.
9. Inspect desktop and mobile UI, service health, and logs.
10. Delete or clearly label acceptance fixtures, scan secrets, commit, push without force, and verify the remote SHA.

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

## 7. Planned Acceptance-Round Changes

- Close the independent checkpoint-field regression coverage gap.
- Remove project-owned Streamlit `use_container_width` deprecations and align the minimum Streamlit version with the replacement API.
- Add repeatable provider acceptance coverage that separates model/text/Responses checks from the paid image check without exposing credentials.
- Ensure both Docker images package every local runtime and provider-acceptance module required at startup and during deployment checks.
- Update this document with final evidence, findings, residual risks, release commit, and CNB remote SHA.

## 8. Residual-Risk Policy

The following may remain only if final review confirms they are not Critical or Important:

- A provider call that defeats socket timeouts can keep one thread occupied until service restart. The task database remains durable and a second worker remains available; restart is the documented local recovery. Process isolation is the future hard-termination boundary.
- Third-party 429/5xx/timeout behavior may still occur. The application must preserve successes, classify the failed item, enforce cooldown, and permit failed-item-only retry where supported.
- Python 3.9 can remain a compatibility test interpreter, but the release runtime must also pass on an actively supported Python version.

## 9. Final Sign-Off

This section is completed only after fresh verification:

- Automated tests: pending
- Live provider checks: pending
- Live image task: pending
- Desktop/mobile browser acceptance: pending
- Security/release scan: pending
- Final Superpowers review: pending
- Release commit: pending
- CNB `main` SHA: pending
- Open Critical findings: pending
- Open Important findings: pending
- Residual Minor/external risks: pending
