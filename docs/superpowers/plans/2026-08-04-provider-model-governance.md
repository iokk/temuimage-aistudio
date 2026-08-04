# Provider Model Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each provider's upstream catalog the default source of selectable models, keep text/vision/image assignments separate, and let users correct inferred capabilities without losing those corrections on refresh.

**Architecture:** Preserve the existing provider JSON and `title_model`, `vision_model`, and `image_model` call paths. Extend normalized catalog entries with inferred and user-overridden roles, merge refreshed upstream entries by model ID, and render a three-step provider workflow: sync, classify, bind.

**Tech Stack:** Python, Streamlit, JSON persistence, unittest.

## Global Constraints

- No new runtime dependency.
- Existing provider records and queued task payloads remain compatible.
- Built-in models are not mixed into a non-empty upstream catalog.
- User role overrides survive catalog refresh.
- No paid image capability probe is performed automatically.

### Task 1: Catalog semantics

**Files:** Modify `app.py`; test `test_provider_models.py`.

- [ ] Add failing tests for upstream-only choices, empty-catalog compatibility fallback, and preserved role overrides.
- [ ] Implement catalog normalization and merge behavior.
- [ ] Verify provider model tests.

### Task 2: Provider settings workflow

**Files:** Modify `app.py`; test `test_provider_models.py`, `test_streamlit_compat.py`.

- [ ] Add tests for role-specific choices and stale assigned models.
- [ ] Render sync status, model capability editor, and three independent bindings.
- [ ] Keep built-in compatibility candidates behind an explicit toggle.
- [ ] Verify provider settings and compatibility tests.

### Task 3: Regression and release

**Files:** Modify `CHANGELOG.md`; create acceptance record.

- [ ] Run compilation, targeted provider tests, full unittest suite, and diff checks.
- [ ] Smoke-test local provider settings without making paid image calls.
- [ ] Commit and push the verified change.
