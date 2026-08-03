# Task 7 Report: Ecommerce Suite Planning Workspace

## Status

Complete. The intelligent combo workflow now uses a two-stage suite workspace and submits an approved frozen plan directly to the existing background task path.

## Delivered

- Output limits are separated from uploads: 1-14 references, default 8 outputs, maximum 10 outputs.
- Added Streamlit-independent suite draft, evidence-supported type, plan-edit, upload-invalidation, and personal-template state helpers.
- Added one-pass structured asset analysis and structured suite planning to `GeminiClient`; `OpenAIClient` inherits both methods.
- Asset analysis is normalized back to stable one-based upload order. Missing, malformed, failed, and demo responses use deterministic local fallbacks.
- AI plan fields include differentiated theme, scene, shot, composition, optional copy, and 1-3 relevant reference IDs. Unsafe or malformed plans fall back through `finalize_suite_plan`.
- AI and user copy, theme, target language, verified selling points, and global instructions now enter the frozen final prompt. Copy remains editable and can be disabled.
- Replaced the old five-tab combo page with stage 1 material/suite setup and stage 2 plan review.
- Stage 1 provides compact upload previews, AI role analysis, manual role correction, product evidence, type counts, conditional verified dimensions, freeform output language, global instructions, personal templates, and output settings.
- Stage 2 restricts type choices to current evidence, exposes all editable plan fields, keeps reference selection resolvable/relevant, shows replacements and warnings, previews selected references, and freezes prompts after every edit.
- Submit writes `combo_suite_draft` and `combo_suite_plan`, invokes the existing `consume_combo_generation_request`, and opens the submitted background task without a generation tab or page polling.
- Added read-only recoverable TEMU system template plus validated, deep-copied, case-insensitive personal template save/load/delete behavior under settings `suite_templates`.
- Upload changes clear prior analysis, product-specific evidence, dimensions, plan widgets, draft, and plan so stale references cannot survive.

## Verification

- TDD RED observed for missing editor/client/template APIs, dropped AI copy, freeform language fallback, stale upload state, over-broad safe types, omitted global instructions, and omitted theme.
- `python3 -m unittest test_suite_workflow -v`: 34 tests passed.
- `python3 -m unittest test_suite_planner -v`: 30 tests passed.
- `python3 -m unittest test_task_center test_task_engine test_task_scheduler test_task_store -v`: 79 tests passed.
- `python3 -m unittest discover -v`: 242 tests passed.
- `python3 -m py_compile app.py suite_planner.py test_suite_workflow.py test_suite_planner.py`: passed.
- `git diff --check`: passed.
- Streamlit `AppTest` demo smoke: stage 1, stage 2, and direct submit/task-center navigation rendered with zero application exceptions.

## Review Notes

- No real provider request is made by the new tests; upstream methods are patched and demo methods short-circuit locally.
- Static format/lint runners `ruff` and `black` are not installed in the current environment; compilation, diff checks, targeted suites, and full discovery were used instead.
- The environment emits existing Python 3.9 end-of-life warnings from Google libraries. They do not fail tests but should be addressed by a runtime upgrade.
