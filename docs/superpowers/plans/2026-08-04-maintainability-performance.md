# 可部署性与页面性能优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TuLite 整理为易部署、易维护、易被后续 AI 接手的正式版本，并降低任务中心、模板库、项目中心和图片结果页在数据量增长后的卡顿。

**Architecture:** 保持 Streamlit + SQLite + 本地数据目录架构不变。文档层建立统一入口、架构说明、故障手册、版本记录和 AI 接手协议；性能层把列表查询与展示拆成分页边界，把图片缩略图、任务轮询和昂贵统计限定在当前页或显式刷新动作内。

**Tech Stack:** Python 3.9+, Streamlit, SQLite, Pillow, Docker Compose, unittest。

## Global Constraints

- 不新增运行时依赖。
- 不改变已有任务载荷、提供商认证和数据目录兼容性。
- 分页默认每页 20 条，允许 10/20/50 条；第一页加载不读取全部原图。
- 任务中心只轮询必要的摘要字段；图片详情在用户展开或进入项目时加载。
- 所有性能改动必须先有可重复的基线测试，再实施最小修复。
- 不提交 `.env`、`data/`、密钥或本地运行日志。

---

### Task 1: 建立仓库治理文档与版本基线

**Files:**
- Modify: `README.md`
- Modify: `DEPLOYMENT.md`
- Create: `ARCHITECTURE.md`
- Create: `MAINTENANCE.md`
- Create: `CHANGELOG.md`
- Create: `docs/PROJECT_STATUS.md`
- Create: `AGENTS.md`

- [ ] 记录当前功能、运行模式、数据目录、升级回滚、备份恢复、健康检查和安全边界。
- [ ] 记录 Streamlit 页面、任务引擎、SQLite、提供商、套图规划和文件存储的数据流。
- [ ] 写入 AI 接手规则：先读哪些文件、不可破坏的契约、测试命令、提交规范和禁止输出凭据。
- [ ] 建立版本号与变更记录，标记本次发布版本。
- [ ] 执行文档内命令的可执行性检查。

### Task 2: 任务中心与模板库分页基线

**Files:**
- Modify: `task_store.py`
- Modify: `app.py`
- Test: `test_task_center.py`, `test_task_store.py`, `test_suite_workflow.py`

- [ ] 先写分页查询和边界测试：总数、页码越界、owner 隔离、排序稳定、空页。
- [ ] 增加仓储层分页接口，返回 `items/total/page/page_size`，避免 UI 读取全量任务。
- [ ] 在任务中心和模板库复用统一分页控件，默认 20 条并保留筛选状态。
- [ ] 验证旧调用仍可读取完整列表，避免破坏后台调度逻辑。

### Task 3: 项目与图片结果按需加载

**Files:**
- Modify: `app.py`
- Modify: `suite_output.py`（仅在已有缩略图能力不足时）
- Test: `test_task_center.py`, `test_suite_apptest.py`

- [ ] 先写测试证明列表视图只使用缩略图/元数据，不在首屏解码全部大图。
- [ ] 增加固定尺寸缩略图缓存键，原图只在预览、下载或展开时读取。
- [ ] 将结果网格固定为响应式 3–4 列，避免单张图片撑满页面。
- [ ] 对项目中心和模板库采用分页或折叠分组，避免一次性渲染全部卡片。

### Task 4: 降低任务轮询和 Streamlit 重跑成本

**Files:**
- Modify: `app.py`
- Modify: `task_engine.py`（仅在需要摘要查询或事件时间戳时）
- Test: `test_task_scheduler.py`, `test_task_center.py`, `test_suite_apptest.py`

- [ ] 先写测试锁定：排队任务显示等待摘要，不重复加载完整结果；只有运行任务或用户主动刷新才更新进度。
- [ ] 将轮询间隔和变更检测绑定到任务摘要版本/更新时间，未变化时不重绘结果区。
- [ ] 保留后台 supervisor 独立运行，不让页面刷新驱动执行。
- [ ] 在无活动任务时停止高频轮询。

### Task 5: 版本验收、部署烟测与发布

**Files:**
- Modify: `docs/superpowers/acceptance/2026-08-04-maintainability-performance-acceptance.md`
- Modify: `Makefile` / `deploy.sh` only if smoke tests expose a gap

- [ ] 运行 `py_compile`、专项测试、全量测试、部署清单测试和 `git diff --check`。
- [ ] 用本地 Streamlit 做桌面和窄视口烟测：任务中心、模板库、项目中心分页和图片网格。
- [ ] 使用 Docker Compose config 校验部署文件；若本机有 Docker，再执行构建健康检查。
- [ ] 更新 CHANGELOG 与验收文档，创建正式版本标签。
- [ ] 推送到 CNB，确认远端分支和标签一致。

