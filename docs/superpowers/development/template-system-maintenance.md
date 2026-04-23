# 模板系统开发与维护规范

## 1. 目的

这份文档用于约束模板系统后续修改方式，避免再次回到以下问题：

1. 页面层直接依赖底层存储结构。
2. 新增模板能力时，只改 UI 不改运行时。
3. 修改模板字段后，没有同步更新设计文档和维护文档。
4. 在系统设置里继续堆逻辑，导致修改风险不断增大。

## 2. 当前模板系统边界

当前模板系统分三层：

1. 存储层
   - `data/templates.json`
   - `data/title_templates.json`
2. 规范化层
   - `get_templates()`
   - `_normalize_template_item()`
   - `_normalize_template_group()`
   - `save_templates()`
3. 产品层
   - 业务工作流分组
   - 模板管理 UI
   - 运行时模板选择与实际生成流程

## 3. 当前模板分组

图片模板分组固定按业务工作流组织：

1. `combo_types`
   - 智能组图模板
2. `smart_types`
   - 快速出图模板
3. `translation_types`
   - 翻译保版模板

标题模板单独维护，不与图片模板混组。

## 4. 修改入口规则

### 4.1 读取模板

不要直接在页面或运行时代码中写：

```python
get_templates()["combo_types"]
```

统一改用：

1. `get_template_group(group_key)`
2. `get_sorted_templates(group_key, enabled_only=False)`
3. `get_enabled_template_group(group_key)`

原因：

1. 这些 helper 会自动吃到规范化后的数据。
2. 后续如果底层结构再收口，不需要全局找散落调用点。

### 4.2 保存模板

不要绕过 `save_templates()` 直接写 `templates.json`。

原因：

1. `save_templates()` 已经负责保存前规范化。
2. 这样可以避免空字段、脏排序、缺省值缺失的问题再次落盘。

## 5. 新增模板字段规范

如果未来新增模板字段，遵循以下顺序：

1. 先更新 `DEFAULT_TEMPLATES`
2. 再更新 `_normalize_template_item()`
3. 再更新模板管理 UI
4. 再更新运行时使用逻辑
5. 最后补文档和测试

不允许只加 UI 字段，不接规范化和运行时。

## 6. 新增模板组规范

如果未来新增新的模板工作流分组，必须同步更新：

1. `DEFAULT_TEMPLATES`
2. `TEMPLATE_GROUP_ORDER`
3. `TEMPLATE_PAGE_META`
4. `TEMPLATE_ITEM_META`
5. 模板管理 UI
6. 对应运行时入口
7. 设计文档与维护文档

否则会出现“配置页可见，但运行时不生效”或“运行时存在，但管理页不可见”的断层。

## 7. 所见即所得阶段规则

当前所见即所得只做到“实时预览型编辑器”，不是完整画布编辑器。

当前允许：

1. 模板卡预览
2. 工作流列表预览
3. Prompt 预览型编辑

当前不允许误判为已具备：

1. 拖拽式编辑
2. 自由布局编辑
3. 组件级画布编辑
4. 模板版本历史对比

如果要进入下一层编辑器能力，必须先更新设计文档边界。

## 8. 运行时接线规则

如果模板会影响真实生成流程，必须满足：

1. 模板可在管理页编辑
2. 模板会被保存到持久层
3. 运行时会读取对应模板
4. 有脚本测试覆盖“修改模板后实际生效”

目前已接线：

1. 翻译保版模板 -> `build_translation_prompt()`

如果未来要接线：

1. 智能组图模板 Prompt
2. 快速出图模板 Prompt
3. 页面级模板可视配置

都必须补相同链路。

## 9. 文档更新规则

每次涉及模板系统变更，至少检查以下文档：

1. `docs/superpowers/specs/2026-04-21-template-management-design.md`
2. `docs/superpowers/specs/2026-04-21-system-detail-design.md`
3. 本文档

当出现以下情况时，必须改文档：

1. 阶段边界变化
2. 新模板组出现
3. 新运行时接线出现
4. 维护规则变化

## 10. 注释规则

模板系统相关代码只在以下地方加注释：

1. 规范化边界
2. 运行时接线点
3. 产品层与存储层解耦点

不要在普通表单字段赋值处加低信息量注释。

## 11. 回归测试最低要求

模板系统相关改动后，至少跑：

1. `python -m py_compile app.py`
2. 模板规范化脚本测试
3. 模板运行时接线测试
4. 页面入口 spot check

如果变更触及：

1. 翻译模板
2. 模板保存逻辑
3. 新模板组

则必须增加对应脚本断言。

## 12. 当前已沉淀的关键函数

模板规范化与读取：

1. `get_templates()`
2. `save_templates()`
3. `get_template_group()`
4. `get_sorted_templates()`
5. `get_enabled_template_group()`
6. `get_title_templates()`
7. `save_title_templates()`
8. `get_enabled_title_templates()`
9. `get_title_template_prompt()`

模板管理 UI：

1. `render_title_template_management()`
2. `render_image_template_management()`
3. `render_template_item_preview()`
4. `render_template_group_preview()`

运行时接线：

1. `build_translation_prompt()`
2. 标题模板读取统一走 `get_title_template_prompt()`
3. 标题模板选择器统一走 `build_title_template_selector_options()`

## 13. 后续建议

下一阶段如果继续推进，优先顺序建议为：

1. 继续拆 `show_settings_center()` 里剩余非模板逻辑
2. 把标题模板也接入统一规范化层
3. 继续统一标题模板/翻译模板的选择器与健康检查
4. 把模板页的预览渲染抽成独立模块
5. 再考虑更完整的编辑器或模板版本管理

- 标题模板与翻译模板的选择器统一走构造 helper，避免页面层各自拼装 option 列表。
