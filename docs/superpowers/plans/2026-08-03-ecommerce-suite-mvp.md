# 电商标准套图 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有“智能组图”升级为可直接使用的电商标准套图工作台：接受 1 至 14 张不完整参考图，生成并允许审核 8 至 10 张差异化计划，后台按计划项独立出图，最终交付 1600×1600 且不超过 2MB 的 PNG/JPG。

**Architecture:** 新增纯领域模块 `suite_planner.py`，集中处理平台预设、素材角色、类型组合、安全替换、参考图选择和最终提示词，避免继续把业务规则散落在 Streamlit 页面中。新增 `suite_output.py` 负责成品规范化。`app.py` 只保留 AI 客户端适配、页面状态、任务持久化和执行编排；任务载荷完整保存计划项，使后台执行、页面恢复和失败重试复用同一提示词与参考图映射。

**Tech Stack:** Python 3.9+, Streamlit, Pillow, SQLite task store, `unittest`。

## Global Constraints

- 不新增依赖，不修改现有提供商认证逻辑，不打印或持久化明文凭据。
- 参考图数量与输出数量解耦：输入 1 至 14 张，输出 1 至 10 张，默认 8 张。
- 每个计划项只能携带 1 至 3 张相关参考图；不同计划项独立调用上游，不使用同提示词的单次 `n=8`。
- 缺少背面、尺寸或细节证据时必须替换类型，禁止生成虚构结构、尺寸或 `XX cm` 占位符。
- 目标语言只作为提示词强调，默认无 LOGO；不对用户文案做额外技术性限制。
- 旧版 combo 任务载荷和失败重试保持可读，已有成功项不重跑。
- `.superpowers/` 是本地视觉草稿，不纳入提交。

---

### Task 1: 锁定套图领域模型和默认组合

**Files:**
- Create: `suite_planner.py`
- Create: `test_suite_planner.py`

**Interfaces:**
- Produces: `TEMU_STANDARD_PROFILE`
- Produces: `build_default_type_counts(target_count=8) -> dict`
- Produces: `normalize_type_counts(type_counts, target_count) -> dict`
- Produces: `validate_suite_draft(draft) -> list[str]`

- [ ] **Step 1: Write failing tests**

覆盖默认 8 张结构、最多 10 张、参考图 1 至 14 张、类型总数与目标数一致、默认无 LOGO、非法数量返回明确验证错误。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_planner.SuitePlannerModelTests -v`

- [ ] **Step 3: Implement immutable profile data and normalization helpers**

使用普通字典和纯函数，类型键固定为 `main-front`、`back-side`、`detail`、`scene`、`dimension`、`selling-point`、`package`、`compare`、`steps`。

- [ ] **Step 4: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_planner.SuitePlannerModelTests -v`

### Task 2: 实现素材归一化、安全替换和差异化计划

**Files:**
- Modify: `suite_planner.py`
- Modify: `test_suite_planner.py`

**Interfaces:**
- Produces: `normalize_assets(raw_assets) -> list[dict]`
- Produces: `plan_suite(draft, ai_plan=None) -> dict`
- Produces: `select_reference_assets(plan_type, assets, limit=3) -> list[str]`

- [ ] **Step 1: Write failing rule tests**

覆盖：背面素材缺失时替换；尺寸数据缺失时替换；细节素材不足时不虚构；每项参考图 1 至 3 张；同类型多张拥有不同主题/镜头/构图；替换理由进入计划项。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_planner.SuitePlannerRuleTests -v`

- [ ] **Step 3: Implement deterministic fallback planning**

先处理需要真实证据的类型，再根据 `detail -> selling-point -> scene` 的安全顺序补位；为重复类型轮换场景、镜头和构图种子，保证离线也能生成有效计划。

- [ ] **Step 4: Add AI result normalization**

仅接受已知类型、已知素材 ID、最多 3 张参考图和非空场景/构图；字段缺失或非法时回落到确定性计划，不能让上游 JSON 破坏规则。

- [ ] **Step 5: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_planner.SuitePlannerRuleTests -v`

### Task 3: 实现提示词组装和真实尺寸约束

**Files:**
- Modify: `suite_planner.py`
- Modify: `test_suite_planner.py`

**Interfaces:**
- Produces: `compose_suite_prompt(plan_item, draft, assets) -> str`
- Produces: `finalize_suite_plan(draft, ai_plan=None) -> dict`

- [ ] **Step 1: Write failing prompt tests**

验证提示词按商品身份、图片类型、场景/构图、用户文案、目标语言、素材角色、平台规范、真实性约束的顺序合并；空文案不生成文案；默认无 LOGO；尺寸图没有真实尺寸时永不进入最终计划；最终提示词不含 `XX cm` 或 `XX inch`。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_planner.SuitePromptTests -v`

- [ ] **Step 3: Implement prompt composition and plan finalization**

用户目标语言作为提示词强调追加，不限制语言枚举；将最终提示词固化在每个计划项中。

- [ ] **Step 4: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_planner.SuitePromptTests -v`

### Task 4: 实现 1600×1600 / 2MB 成品规范化

**Files:**
- Create: `suite_output.py`
- Create: `test_suite_output.py`

**Interfaces:**
- Produces: `normalize_suite_image(source, destination_dir, stem, prefer_png=False) -> dict`

- [ ] **Step 1: Write failing image-output tests**

用内存生成横图、竖图、RGBA 图和高噪声图，验证不裁切的等比 contain/pad、固定 1600×1600、PNG/JPG、≤2MB、72 DPI 元数据、返回路径/尺寸/格式/字节数。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_output -v`

- [ ] **Step 3: Implement adaptive encoding**

照片型输出优先 JPG，透明或文字型可选 PNG；JPG 从高质量逐级压缩，必要时统一落 JPG，超过 2MB 时继续降低质量但不改变像素尺寸。

- [ ] **Step 4: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_output -v`

### Task 5: 将完整计划持久化到 combo 任务

**Files:**
- Modify: `app.py`
- Create: `test_suite_workflow.py`

**Interfaces:**
- Consumes: `finalize_suite_plan()`
- Produces: `build_suite_task_requests(plan, persisted_assets) -> list[dict]`
- Extends: combo payload with `suite_version`, `suite_draft`, `suite_plan`, `reqs`

- [ ] **Step 1: Write failing workflow tests**

验证每个请求保存计划项 ID、最终提示词、1 至 3 个素材路径、类型和展示标题；任务创建后不依赖 `st.session_state`；旧 `reqs` 载荷仍通过验证。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_workflow.SuitePayloadTests -v`

- [ ] **Step 3: Implement request building and payload validation**

复用现有 durable upload 持久化逻辑，用稳定素材 ID 映射到保存路径；将批准计划原样写进任务载荷。

- [ ] **Step 4: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_workflow.SuitePayloadTests -v`

### Task 6: 按计划项执行、规范化输出并保留可重试信息

**Files:**
- Modify: `app.py`
- Modify: `test_suite_workflow.py`
- Modify: `test_failed_item_retry.py`

**Interfaces:**
- Modifies: `_execute_combo_task(execution)`
- Modifies: `get_combo_retry_request(task, item)`
- Consumes: `normalize_suite_image()`

- [ ] **Step 1: Write failing execution tests**

验证每个子项仅收到自身选择的参考图与固化提示词；成功结果包含计划项 ID 和成品元数据；失败结果始终保存完整 `req`；部分失败后只重试失败项且参考图/提示词/计划 ID 不漂移。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_workflow.SuiteExecutionTests test_failed_item_retry.FailedItemRetryTests -v`

- [ ] **Step 3: Implement per-item execution and output normalization**

继续沿用现有任务引擎、超时、冷却和并发保护；只有新 `suite_version` 任务强制执行成品规范化，旧任务保持原行为。

- [ ] **Step 4: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_workflow.SuiteExecutionTests test_failed_item_retry.FailedItemRetryTests -v`

### Task 7: 构建双阶段工作台和个人模板

**Files:**
- Modify: `app.py`
- Modify: `test_suite_workflow.py`

**Interfaces:**
- Produces: `build_suite_editor_state(...) -> dict`
- Produces: `save_personal_suite_template(name, type_counts) -> None`
- Produces: `load_personal_suite_templates() -> list[dict]`

- [ ] **Step 1: Write failing UI-state tests**

验证默认 8 张、总数上限 10、参考图角色可纠正、尺寸输入只在尺寸图启用时需要、目标语言自由文本、计划卡可修改类型/场景/构图/文案/参考图、模板能保存和恢复系统默认。

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest test_suite_workflow.SuiteEditorStateTests -v`

- [ ] **Step 3: Replace the existing five-tab combo form**

阶段一显示素材、商品摘要、类型卡和组合；阶段二显示可编辑计划卡、风险/替换理由及“提交后台任务”。已提交后跳转任务中心，页面不通过高频全页刷新驱动任务。

- [ ] **Step 4: Implement personal template persistence**

复用现有 `save_settings()` / config JSON，新增独立 `suite_templates` 键；系统预设只读，个人模板可保存和删除。

- [ ] **Step 5: Run focused tests and confirm green**

Run: `python3 -m unittest test_suite_workflow.SuiteEditorStateTests -v`

### Task 8: 回归、验收记录和本地打开

**Files:**
- Create: `docs/superpowers/acceptance/2026-08-03-ecommerce-suite-mvp-acceptance.md`
- Modify: relevant files only for acceptance fixes

- [ ] **Step 1: Run static and complete automated validation**

Run: `python3 -m py_compile app.py suite_planner.py suite_output.py task_engine.py task_store.py`

Run: `python3 -m unittest test_suite_planner test_suite_output test_suite_workflow test_failed_item_retry -v`

Run: `python3 -m unittest discover -v`

- [ ] **Step 2: Start Streamlit and execute browser acceptance**

Run: `python3 run_tulite.py`

验收桌面与移动视口：双阶段流程可达；默认 8 张；可调至 10；多参考图角色和每卡选图可编辑；无尺寸时明确替换；提交后任务中心可见且后台运行；结果网格不会让单张图片占满屏幕。

- [ ] **Step 3: Record evidence**

在验收文档中记录测试命令、通过数、浏览器视口、任务载荷样例（不含凭据）、未执行真实计费调用时的说明和剩余风险。

- [ ] **Step 4: Review the final diff and restart cleanly**

Run: `git diff --check`

Run: `git status --short`

停止旧的本地 TuLite 进程，重新启动在 `127.0.0.1:8501`，确认健康响应后在应用内浏览器打开。

