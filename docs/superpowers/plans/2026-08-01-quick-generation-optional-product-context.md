# 快速出图可选商品上下文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许快速出图在没有商品名称时基于参考图提交，并将可选补充提示词写入所有最终出图指令。

**Architecture:** 保持任务载荷向后兼容，在 UI 层统一计算提交资格；在后台任务执行层将非空补充提示词附加给每一个已经由模板生成的最终提示词。参考图保真规则保持最后的产品身份边界。

**Tech Stack:** Python 3.9+, Streamlit, `unittest`, SQLite 任务引擎。

## Global Constraints

- 不增加依赖。
- 参考图、任务类型和既有翻译工作流的验证语义不变。
- 新增提示词字段为可选；旧任务缺少该字段时输出不变。
- 测试通过公开任务执行和提交资格边界验证行为，不发送真实上游请求。

---

### Task 1: 锁定提交资格与提示词传递

**Files:**
- Modify: `test_task_scheduler.py`
- Modify: `app.py`

**Interfaces:**
- Produces: `can_submit_smart_generation(images, workflow_mode, total_count) -> bool`
- Produces: `append_smart_generation_instruction(base_prompt, user_instruction) -> str`

- [ ] **Step 1: Write the failing tests**

```python
self.assertTrue(app.can_submit_smart_generation([object()], "creative", 1))
self.assertFalse(app.can_submit_smart_generation([object()], "creative", 0))
self.assertIn("USER CREATIVE DIRECTION", app.append_smart_generation_instruction("base", "强调密封杯盖"))
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python3 -m unittest test_task_scheduler.SmartGenerationInputTests -v`
Expected: FAIL because the two public helpers do not exist.

- [ ] **Step 3: Write the minimal implementation**

```python
def can_submit_smart_generation(images, workflow_mode, total_count):
    return bool(images) and (workflow_mode == "translate" or total_count > 0)
```

`append_smart_generation_instruction()` returns the original prompt for blank input and otherwise appends a bounded user-direction section that retains reference-image identity.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `python3 -m unittest test_task_scheduler.SmartGenerationInputTests -v`
Expected: PASS.

### Task 2: 接入快速出图页面和后台任务

**Files:**
- Modify: `app.py`
- Test: `test_task_scheduler.py`

**Interfaces:**
- Consumes: `can_submit_smart_generation()` and `append_smart_generation_instruction()`.
- Produces: optional `user_instruction` in new smart-task payloads.

- [ ] **Step 1: Write the failing task-execution test**

```python
task["payload"]["user_instruction"] = "Use a clean kitchen counter scene"
result = app._execute_smart_task(execution)
self.assertIn("Use a clean kitchen counter scene", client.image_prompts[0])
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python3 -m unittest test_task_scheduler.SmartGenerationInstructionTests -v`
Expected: FAIL because the instruction is not yet added to item prompts.

- [ ] **Step 3: Write the minimal implementation**

Use the submission helper for `can_gen`, render optional product fields and a `st.text_area` for `user_instruction`, persist it in the smart task payload, and append it immediately after `compose_image_prompt()`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python3 -m unittest test_task_scheduler.SmartGenerationInputTests test_task_scheduler.SmartGenerationInstructionTests -v`
Expected: PASS.

### Task 3: Full regression and visual acceptance

**Files:**
- Modify: `docs/superpowers/acceptance/2026-08-01-quick-generation-optional-product-context.md`

- [ ] **Step 1: Run the complete Python suite**

Run: `python3 -m unittest discover -v`
Expected: all tests pass.

- [ ] **Step 2: Start or refresh the local service and inspect the quick-generation page**

Expected: no horizontal overflow, optional labels are visible, button state follows images/types rather than product name.

- [ ] **Step 3: Record acceptance evidence and commit**

Run: `git status --short`, then commit the code, tests, design, plan, and acceptance record with `feat: make quick generation product context optional`.

- [ ] **Step 4: Push normally and verify the remote head**

Run: `git push cnb main` followed by `git ls-remote cnb refs/heads/main`.
Expected: remote SHA equals local `HEAD`.
