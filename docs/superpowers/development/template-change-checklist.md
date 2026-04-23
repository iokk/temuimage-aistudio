# 模板系统改动检查清单

在修改模板系统前、中、后，按这个清单执行，确保形成闭环。

## 1. 改动前

1. 阅读：
   - `docs/superpowers/specs/2026-04-21-template-management-design.md`
   - `docs/superpowers/development/template-system-maintenance.md`
2. 确认这次改动属于哪个阶段：
   - 阶段 1：模板管理能力
   - 阶段 2：所见即所得编辑器
   - 阶段 3：更深层结构治理
3. 确认是否会影响真实运行时：
   - 仅 UI
   - 仅存储
   - UI + 存储 + 运行时

## 2. 改动中

1. 读模板必须优先使用：
   - `get_template_group()`
   - `get_sorted_templates()`
   - `get_enabled_template_group()`
2. 存模板必须优先使用：
   - `save_templates()`
   - `save_title_templates()`
3. 选择标题模板时，优先复用：
   - `build_title_template_selector_options()`
4. 新增字段时必须同步：
   - 默认值
   - 规范化逻辑
   - UI
   - 运行时
5. 不要把模板逻辑直接塞回 `show_settings_center()`。

## 3. 改动后

至少执行：

1. `python -m py_compile app.py`
2. 模板规范化测试
3. 运行时接线测试
4. 页面入口 spot check

如果改动影响翻译模板，还要确认：

1. 修改后的 `prompt` 确实进入 `build_translation_prompt()`
2. 禁用模板后不会被错误选中

如果改动影响标题模板，还要确认：

1. 修改后的模板能通过 `get_title_template_prompt()` 被业务页面读取
2. 禁用模板后不会继续出现在模板选择器里
3. 关键占位符如 `{product_info}` 不会被误删导致模板失效

## 4. 文档同步

发生以下情况时必须改文档：

1. 新阶段开始
2. 阶段边界变化
3. 新模板组出现
4. 新运行时接线出现
5. 新规范化规则出现

至少同步：

1. `docs/superpowers/specs/2026-04-21-template-management-design.md`
2. `docs/superpowers/development/template-system-maintenance.md`
3. 本清单

## 5. 结束条件

只有当以下都满足时，才算这次模板系统改动完成：

1. 代码通过基础检查
2. 运行时行为符合预期
3. 页面没有明显结构回退
4. 文档已经同步
5. 后续维护者能从文档和 helper 找到正确修改入口
