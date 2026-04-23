# 电商出图工作台桌面化重构设计

- 日期: 2026-04-22
- 项目: 电商出图工作台
- 设计主题: Electron 原生桌面客户端 + 本地 Python/FastAPI 核心 + SQLite/文件存储
- 设计目标: 在不兼容旧数据的前提下，重构为可安装、可维护、可持续迭代的 Mac 优先桌面应用

## 1. 背景

当前系统已经具备完整业务能力，但其实现形态是以 Streamlit 单体应用为主的本地工具，UI、业务逻辑、任务执行、数据存储、文件管理高度耦合，不适合作为长期维护的桌面产品继续演进。

现阶段的产品目标已经明确：

1. 首版以 `Mac` 为优先交付平台。
2. 首版不是缩水 MVP，而是要完整覆盖现有主要功能面。
3. 新客户端允许重构交互，不要求沿用当前 Streamlit 页面心智。
4. 用户应当下载安装后直接打开使用，只需填写自己的 API Key。
5. 不要求兼容旧版本地数据，允许采用全新架构。
6. 技术上采用 `Electron 前端壳 + 本地 Python/FastAPI 核心 + SQLite/文件存储`。

本设计的目标不是对旧项目做局部修补，而是定义一套新的桌面产品架构，使其具备以下特征：

1. 功能完整。
2. 结构清晰。
3. 易于调试与扩展。
4. 适合后续继续做界面重构、桌面分发、甚至未来线上化演进。

## 2. 目标与非目标

### 2.1 目标

1. 将当前产品重构为 `Electron` 驱动的原生桌面客户端。
2. 使用 `React + TypeScript + Vite` 承担新的前端界面层。
3. 使用 `FastAPI` 作为本地业务 API 层，替代 Streamlit 页面承载业务。
4. 使用 `Python Worker` 承担图片生成、标题生成、翻译、归档等耗时任务。
5. 使用 `SQLite` 替代 JSON 文件作为结构化数据真相源。
6. 使用标准应用目录保存文件、日志、缓存和导出物。
7. 实现安装后即可用，不依赖用户自行安装 Python。
8. 完整承接现有功能面：
   - 智能组图
   - 快速出图
   - 图片翻译
   - 标题生成
   - 项目中心
   - 模板库
   - 提供商设置
   - 系统设置与诊断

### 2.2 非目标

1. 不兼容旧版本地 JSON 数据和旧项目目录结构。
2. 不在首版引入账号系统、云同步或多人协作。
3. 不在首版引入插件系统。
4. 不在首版引入复杂自动更新系统。
5. 不在首版支持 Windows 同发。
6. 不追求任务断点续跑。

## 3. 核心决策

本轮架构设计中，以下决策视为已拍板：

1. 桌面壳使用 `Electron`。
2. 前端使用 `React + TypeScript + Vite`。
3. Electron 构建与打包使用 `Electron Forge`。
4. 本地后端使用 `FastAPI`。
5. 任务执行由 Python Worker 负责。
6. 结构化数据使用 `SQLite`。
7. 文件存储使用应用数据目录中的本地文件系统。
8. 业务能力通过本地 HTTP API 暴露。
9. 桌面系统能力通过 `preload + IPC` 暴露。
10. 密钥不以明文写入 SQLite。
11. 首版平台为 `Mac`。
12. 首版交付体验为“下载安装后直接可用”。

## 4. 总体架构

系统拆分为 6 层：

1. `Electron Main`
2. `Electron Preload`
3. `Renderer`
4. `Local FastAPI`
5. `Python Worker Layer`
6. `SQLite + App Files`

整体调用链分为两条：

### 4.1 业务链路

`Renderer -> FastAPI -> Service -> Repository / Worker`

用于：

1. Provider 管理
2. 模板管理
3. 工作流提交
4. 任务查询
5. 项目中心
6. 设置与诊断

### 4.2 桌面能力链路

`Renderer -> Preload -> Electron Main`

用于：

1. 文件选择
2. 目录选择
3. 打开 Finder
4. 应用版本信息
5. 本地日志目录
6. 安全密钥读写
7. 运行时状态查询

### 4.3 架构原则

1. UI 不直接接触 Python 文件系统能力。
2. Electron 不承载业务规则。
3. FastAPI 不承载 UI 状态。
4. Worker 不感知前端页面结构。
5. SQLite 是唯一结构化真相源。
6. 文件系统是二进制产物与附件层。

## 5. 模块边界与目录结构

推荐目录结构如下：

```text
desktop-app/
  client/
    electron/
      src/
        main/
        preload/
        shared/
      forge.config.ts
      package.json

    renderer/
      src/
        app/
        pages/
        features/
        components/
        hooks/
        lib/
        styles/
      package.json

  python/
    app/
      api/
      core/
      db/
      models/
      repositories/
      services/
      workers/
      utils/
    main.py
    requirements.txt

  resources/
    icons/
    defaults/
    prompts/
    templates/

  scripts/
  docs/
```

### 5.1 Electron Main

职责：

1. 创建和管理窗口。
2. 启动与关闭本地 Python/FastAPI 服务。
3. 提供应用生命周期管理。
4. 暴露系统菜单、对话框、应用信息。
5. 处理系统级能力，如路径打开、文件选择、安全存储。
6. 汇总桌面层日志。

限制：

1. 不处理业务流程。
2. 不直接写 SQLite 业务数据。
3. 不执行图片生成等重型任务。

### 5.2 Electron Preload

职责：

1. 暴露白名单桌面能力给 Renderer。
2. 使用 `contextBridge` 建立安全边界。

示例能力：

1. `selectFiles`
2. `selectDirectory`
3. `openPath`
4. `getAppInfo`
5. `getRuntimeStatus`
6. `saveSecret`
7. `readSecret`

### 5.3 Renderer

职责：

1. 承载新的桌面产品界面。
2. 管理用户交互和页面状态。
3. 调用 FastAPI 获取业务状态。
4. 调用 Preload 获取桌面能力。

限制：

1. 不直接访问 Node。
2. 不直接读写数据库。
3. 不直接启动 Python 任务。

### 5.4 FastAPI

职责：

1. 暴露本地业务 API。
2. 参数校验。
3. 服务编排。
4. 任务创建与查询。
5. 项目与模板操作。
6. 诊断结果汇总。

限制：

1. 不直接承载页面。
2. 不在 Router 中堆积业务逻辑。
3. 不把重型任务长期阻塞在请求线程内。

### 5.5 Python Worker

职责：

1. 执行智能组图。
2. 执行快速出图。
3. 执行图片翻译。
4. 执行标题生成。
5. 执行 ZIP 重建与文件扫描等异步任务。

### 5.6 Repository

职责：

1. 管理 SQLite 读写。
2. 管理文件记录索引。
3. 屏蔽底层存储细节。

## 6. 数据架构

### 6.1 数据真相划分

结构化真相：

1. `SQLite`

二进制产物与附件：

1. `项目输入图片`
2. `生成结果图片`
3. `ZIP`
4. `日志`
5. `缓存`

### 6.2 SQLite 核心表

建议的核心表如下：

1. `providers`
2. `settings`
3. `template_groups`
4. `templates`
5. `projects`
6. `project_files`
7. `tasks`
8. `task_events`
9. `diagnostic_snapshots`

### 6.3 表设计原则

1. `providers` 存元数据，不存明文 API Key。
2. `settings` 使用 key-value 结构承载系统配置。
3. `templates` 统一承载标题、图片、翻译模板。
4. `projects` 承载项目中心的主记录。
5. `project_files` 承载文件级索引与角色定义。
6. `tasks` 承载任务状态机与调度入口。
7. `task_events` 承载进度与事件流。

### 6.4 项目状态模型

项目由两条状态线组成：

#### 任务运行状态

1. `queued`
2. `preparing`
3. `running`
4. `succeeded`
5. `failed`
6. `cancel_requested`
7. `cancelled`

#### 记录存储状态

1. `active`
2. `trashed`
3. `purged`

### 6.5 文件存储布局

应用数据目录建议结构如下：

```text
~/Library/Application Support/EcommerceWorkbench/
  app.db
  logs/
  cache/
  files/
    projects/
      <project-id>/
        inputs/
        outputs/
        exports/
        meta/
    temp/
```

说明：

1. `app.db` 为主数据库。
2. `logs/` 保存 Electron、API、Worker 日志。
3. `cache/` 保存临时结果与中间缓存。
4. `projects/<project-id>/inputs` 保存用户输入素材。
5. `outputs` 保存生成图。
6. `exports` 保存 ZIP、标题文本等导出物。
7. `meta` 可保存非真相源的辅助调试数据。

## 7. 任务系统设计

### 7.1 总体模型

建议采用：

`API 创建任务 -> SQLite 落任务 -> Worker 拉取执行 -> 持续写入事件与进度 -> 项目归档`

### 7.2 任务类型

1. `smart_generate`
2. `quick_generate`
3. `image_translate`
4. `title_generate`
5. `zip_rebuild`
6. `file_scan`
7. `trash_cleanup`
8. `provider_test`

### 7.3 队列策略

首版采用稳定优先的并发策略：

1. `heavy queue`
   - 智能组图
   - 快速出图
   - 图片翻译
2. `light queue`
   - 标题生成
   - Provider 测试
   - 诊断
   - ZIP 重建

建议规则：

1. 同时最多 2 个重型任务。
2. 轻量任务可排队，但不抢占重型位。
3. 同一项目同一时刻仅允许一个活动生成任务。
4. 不允许无限队列堆积。

### 7.4 取消与恢复策略

1. 支持取消任务。
2. 不要求断点续跑。
3. 中间结果可保留。
4. 用户可基于历史项目重新发起。

## 8. FastAPI 接口设计

业务接口统一采用版本前缀：

`/api/v1/*`

### 8.1 接口分组

1. `/api/v1/providers`
2. `/api/v1/settings`
3. `/api/v1/templates`
4. `/api/v1/tasks`
5. `/api/v1/projects`
6. `/api/v1/diagnostics`
7. `/api/v1/workflows`

### 8.2 工作流接口原则

工作流接口只负责：

1. 校验输入。
2. 创建任务。
3. 返回任务 ID。

不负责：

1. 同步长时间阻塞执行。

### 8.3 任务查询方式

首版采用轮询：

1. `GET /api/v1/tasks`
2. `GET /api/v1/tasks/{id}`
3. `GET /api/v1/tasks/{id}/events`
4. `POST /api/v1/tasks/{id}/cancel`

### 8.4 错误模型

统一错误结构：

```json
{
  "error": {
    "code": "PROVIDER_INVALID",
    "message": "提供商配置无效",
    "details": {},
    "retryable": false
  }
}
```

要求：

1. 前端不依赖 Python 原始异常字符串做控制流。
2. 错误码稳定。
3. 错误信息可读。
4. 可选附带技术细节。

## 9. 前端信息架构与交互设计

### 9.1 主导航

建议新桌面客户端主导航为：

1. `创作中心`
2. `项目中心`
3. `模板库`
4. `提供商`
5. `系统设置`

### 9.2 创作中心

创作中心承载四大工作流：

1. 智能组图
2. 快速出图
3. 图片翻译
4. 标题生成

建议采用：

1. 左侧二级导航切换工作流。
2. 中间为表单与结果主工作区。
3. 右侧为上下文面板，展示当前 Provider、任务状态、最近项目与常用模板。

### 9.3 项目中心

项目中心承载：

1. 进行中
2. 历史项目
3. 回收站
4. 文件管理

建议布局：

1. 顶部筛选栏
2. 左侧项目列表
3. 中间详情区
4. 右侧操作面板

### 9.4 模板库

模板库按资产编辑器设计：

1. 左侧模板分类树
2. 中间模板列表
3. 右侧模板详情与预览

### 9.5 提供商

Provider 页面聚焦：

1. 默认提供商概览
2. Provider 列表
3. 新增 / 编辑 Drawer
4. 测试连接结果
5. 密钥状态

### 9.6 系统设置

系统设置按设置组拆分：

1. 常规
2. 默认生成设置
3. 存储
4. 网络
5. 诊断
6. 关于

## 10. 安全与密钥设计

### 10.1 Electron 安全边界

必须满足：

1. `nodeIntegration = false`
2. `contextIsolation = true`
3. 只通过 `preload + contextBridge` 暴露桌面能力
4. Renderer 不直接接触 Node API

### 10.2 API Key 存储

策略：

1. SQLite 中仅保存 `secret_ref`。
2. 明文 API Key 进入系统安全存储。
3. 日志中不打印 Key。
4. 错误信息不回显完整凭证。

推荐执行路径：

1. Renderer 提交 Provider 表单。
2. Electron Main 将密钥写入安全存储。
3. FastAPI/Service 记录 Provider 元数据与 `secret_ref`。
4. 任务执行时从安全适配层取出密钥。

### 10.3 本地服务访问边界

1. FastAPI 仅监听 `127.0.0.1`。
2. 不对局域网开放。
3. 不对外暴露远程访问入口。

## 11. 运行时与打包设计

### 11.1 首版运行时目标

用户体验为：

1. 下载 `.dmg`
2. 安装 `.app`
3. 启动后直接进入客户端
4. 填写 API Key 后开始使用

### 11.2 Python 运行时策略

首版采用：

1. 应用包内置 Python runtime
2. 应用包内置 Python App
3. 不依赖用户本机 Python
4. 不要求用户首次启动下载依赖

### 11.3 App 包结构

建议 Electron 资源目录中包含：

```text
MyApp.app/
  Contents/
    Resources/
      python/
        runtime/
        app/
        resources/
```

### 11.4 启动流程

1. Electron 启动。
2. 初始化应用数据目录。
3. 检查 SQLite 与 migration。
4. 启动 Python/FastAPI。
5. 做健康检查。
6. 健康检查通过后加载主窗口。

### 11.5 启动状态页

建议提供专门启动状态页，覆盖以下状态：

1. 正在初始化应用数据
2. 正在启动本地服务
3. 正在检查运行环境
4. 启动成功
5. 启动失败，可查看日志或重试

## 12. 诊断与可维护性设计

### 12.1 诊断页面

建议至少包含：

1. 运行环境状态
2. Provider 检查
3. 文件健康检查
4. 模板健康检查
5. 最近错误摘要
6. 日志目录入口
7. 诊断包导出

### 12.2 日志体系

至少包含：

1. `electron-main.log`
2. `python-api.log`
3. `worker.log`

### 12.3 诊断包导出

建议导出：

1. 应用版本
2. 系统信息
3. 数据库基础统计
4. 最近错误摘要
5. 日志文件
6. 非敏感配置快照

限制：

1. 默认脱敏
2. 不导出明文 API Key
3. 不强制导出用户原始图片

### 12.4 Migration 策略

1. 首版即使用数据库 migration 工具。
2. 每次 schema 变更有明确版本号。
3. 启动时自动检查并执行 migration。
4. migration 失败时进入错误页，不以半损坏状态继续运行。

## 13. 默认资源策略

需要版本化管理的默认资源包括：

1. 默认模板
2. 默认 Prompt
3. 默认设置

原则：

1. 内置默认资源带版本号。
2. 用户修改资源与内置默认资源分离。
3. 升级时不强制覆盖用户自定义内容。
4. 支持恢复默认资源。

## 14. 实施顺序

建议按 6 个阶段推进：

### 阶段 0：冻结旧系统、提炼可迁移核心

产出：

1. 功能清单
2. 数据清单
3. 旧逻辑映射表
4. 新模块清单

### 阶段 1：搭建新骨架

目标：

1. Electron、Renderer、FastAPI、SQLite 全链路启动成功。

完成标准：

1. 打开 App 后可见新前端。
2. 前端可调用 FastAPI 并获得系统信息。
3. 后端启动失败时前端有明确错误状态。

### 阶段 2：先做平台底座

包括：

1. Provider 管理
2. 密钥存储
3. 设置系统
4. 模板存储模型
5. 任务/项目数据模型
6. 应用文件目录
7. 统一 API Client
8. 桌面文件能力

### 阶段 3：先打通一个完整工作流

推荐先做：

1. 标题生成

目标：

1. 验证从提交任务到结果归档的完整链路。

### 阶段 4：补齐全部创作工作流

顺序建议：

1. 标题生成
2. 图片翻译
3. 快速出图
4. 智能组图

### 阶段 5：补齐管理能力

包括：

1. 项目中心
2. 回收站
3. 文件管理
4. 模板库
5. 诊断与批量操作

### 阶段 6：桌面交付打磨

包括：

1. 启动页与错误页
2. 打包产物
3. 内测修复
4. 签名 / 公证准备

## 15. 里程碑

建议以 4 个里程碑管理：

1. `M1：桌面骨架跑通`
2. `M2：一个工作流跑通`
3. `M3：创作中心完整`
4. `M4：完整桌面产品可分发`

## 16. 风险与应对

### 16.1 风险

1. 桌面壳完成快于业务迁移，导致壳新而功能空。
2. 将旧单体逻辑原样复制进新架构。
3. API、Service、Worker 边界混乱。
4. Electron 侵入业务层。
5. SQLite 与文件系统双写不一致。
6. 本地重型任务并发失控。
7. 内置 Python runtime 在用户机器上启动不稳。
8. 范围完整但阶段拆分不清，导致版本长期无法交付。

### 16.2 应对

1. 坚持“骨架 -> 一个工作流 -> 全功能”的迁移节奏。
2. 新架构只迁移业务能力，不迁移旧页面状态组织。
3. 强制 Service 作为业务编排层。
4. Electron 只做桌面宿主。
5. 项目归档必须通过统一 Service 完成。
6. 首版并发策略保守，稳定优先。
7. 尽早验证打包后的 runtime、路径解析和健康检查。
8. 严格执行里程碑拆分。

## 17. 最终判断

基于当前决策，本方案已满足以下执行条件：

1. 技术路线明确。
2. 范围边界明确。
3. 平台与交付体验明确。
4. 架构边界明确。
5. 实施顺序明确。
6. 风险与应对明确。

结论：

当前架构已经达到“可进入实施计划”的状态。

下一步不应继续抽象讨论，而应基于本设计文档进入实施规划与任务拆解。
