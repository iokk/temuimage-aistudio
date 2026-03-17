# 🍌 TEMU AI Studio V1.0.0

> V1.0 收敛版：批量出图、快速出图、图片翻译、Vertex Express 支持

## ✨ V1.0.0 版本说明

| 功能 | 说明 |
|------|------|
| 模型统一 | 所有出图链路固定为 `🍌 Nano Banana 2` |
| API 兼容 | 支持 Gemini API Key 与 Vertex Express Key |
| 速率稳定性 | 增加请求并发闸门 + 抖动退避重试 |
| 界面收敛 | 导航与页面标题更简洁，面向实际出图流程 |
| 出图统计 | 后台累计/今日出图指标，前台页底显示“今日已出图” |

## ✨ V15.3.7 优化内容

| 功能 | 说明 |
|------|------|
| 登录免重复填写 | 支持固定管理员/用户密码启动注入，重部署无需手工重填 |
| API Key免重复填写 | 支持 `SYSTEM_API_KEYS_FIXED` 启动注入，可按策略自动同步 |
| 后台权限收敛 | 管理后台严格管理员访问；系统用户可配置免密直进业务页面 |

## ✨ V15.3.6 优化内容

| 功能 | 说明 |
|------|------|
| 默认模型升级 | 图片生成与图片翻译默认切换为 `🍌 Nano Banana 2` |
| 接口稳定性 | 增加超时识别与重试退避，减少 `DEADLINE_EXCEEDED` 失败 |
| 英文一致性 | 强制英文模式下，出图会自动做英文残留校验并重试 |

## ✨ V15.3.4 优化内容

| 功能 | 说明 |
|------|------|
| 图片翻译结果页瘦身 | 默认仅展示译后图，不再强制原图对照 |
| 下载交互简化 | 勾选下载改为集中勾选，批量直接打包 ZIP |
| 卡顿问题修复 | 移除 PNG/JPG 切换与原图重复转码，减少重载 |
| ZIP按需缓存 | 同一勾选集不重复打包，响应更快 |

## ✨ V15.3.5 优化内容

| 功能 | 说明 |
|------|------|
| 翻译速度优化 | 文本链路新增“极速模式”（OCR+翻译单次请求） |
| 文本并发处理 | 仅文本翻译支持并发线程，提高批量吞吐 |
| 模型策略收敛 | 当前统一锁定 Nano Banana 2，减少模型切换带来的不稳定 |
| 处理过程减负 | 降低实时日志刷新频率，减少前端卡顿 |

## ✨ V15.3.3 优化内容

| 功能 | 说明 |
|------|------|
| 翻译链路升级 | 图片翻译默认切到 Nano Banana 2 |
| 自动分批 | 翻译任务按批次自动拆分 |
| 流程指引 | 智能组图/快速出图增加步骤提示 |

## ✨ V15.3.2 优化内容

| 功能 | 说明 |
|------|------|
| 稳定性提示 | 参考图选择与异常恢复建议 |
| 会话清理 | 侧边栏一键清理会话缓存 |

## ✨ V15.3 新增内容

| 功能 | 说明 |
|------|------|
| 图片翻译模块 | 上传电商图片，自动提取图中文字并翻译 |
| 翻译出图 | 一键生成目标语言版本图片 |
| 独立页面 | 图片翻译功能独立入口，操作更清晰 |

## 🔧 V15.2.1 修复内容

| 问题 | 原因 | 修复方案 |
|------|------|----------|
| 1. `thinking_level not supported` 错误 | Flash模型不支持thinking参数 | 检测模型类型，仅Pro模型使用thinking_config |
| 2. 图片生成后无法显示 | 结果未存入session_state | 使用`combo_results`保存，完成后刷新显示 |
| 3. 无法下载/批量打包 | ZIP生成逻辑问题 | 新增`create_zip_from_results()`统一处理 |
| 4. 文件名无类型 | 仅用序号 | 改为`01_卖点图.png`格式 |
| 5. Token消耗不显示 | 未在完成后显示 | 添加token-badge显示 |
| 6. 生成卡住不动 | 异常被静默 | 实时日志+详细错误信息 |

## 🤖 模型支持说明

| 模型 | 分辨率 | 参考图 | 推理深度 |
|------|--------|--------|----------|
| 🍌 Nano Banana 2 (`gemini-3.1-flash-image-preview`) | 1K | 5张 | minimal / high |

> **注意**: 当前版本已将出图模型固定为 `Nano Banana 2`，不再在页面提供 Pro/Flash 切换。

## ✨ V15.2 新增/优化功能

### 📸 图片生成优化
- **实时日志**: 每张图片生成成功/失败都有即时反馈
- **错误详情**: 显示具体错误原因，方便排查
- **类型命名**: 文件自动命名为 `01_主图白底.png`、`02_功能卖点.png` 等
- **结果持久化**: 生成完成后结果保存在session中，刷新不丢失

### 🏷️ 标题生成优化 (中英双语)
```
输出格式 (6行):
[English Title 1 - 180-250字符]
[中文标题1]
[English Title 2 - 180-250字符]
[中文标题2]
[English Title 3 - 180-250字符]
[中文标题3]
```

### 标题模板规则
- **英文字符**: 180-250字符 (TEMU最佳曝光区间)
- **中文翻译**: 自然准确的中文对照
- **三种策略**: 搜索优化 / 转化优化 / 差异化
- **无特殊符号**: 纯文本，字母+数字+空格

### 管理后台优化
- 标题模板修改后**全局生效**
- 可添加自定义模板
- 支持恢复默认模板

## 📦 部署说明（简化版）

### GitHub → Zeabur 拉取部署

推荐做法：

1. 代码推送到 GitHub 仓库
2. 在 Zeabur 新建服务并连接该仓库
3. 在服务变量里写入：

```bash
SYSTEM_API_KEYS_FIXED=AQ.xxxxx
SYSTEM_API_KEYS_SYNC_MODE=replace
GOOGLE_GENAI_USE_VERTEXAI=true
ADMIN_PASSWORD_FIXED=你的管理员密码
USER_PASSWORD_FIXED=你的用户密码
ALLOW_PASSWORDLESS_USER_LOGIN=true
PORT=8501
```

这样后续只需要 `git push`，Zeabur 就能直接拉取更新。

### 一键启动（推荐）

```bash
# 1) 进入项目目录
cd temu-v15.2-fixed

# 2) 启动（自动创建 .env 与 data 目录）
./scripts/deploy-quick.sh up

# 3) 访问
# http://localhost:8501
```

### 常用运维命令

```bash
./scripts/deploy-quick.sh status
./scripts/deploy-quick.sh logs
./scripts/deploy-quick.sh restart
./scripts/deploy-quick.sh down
```

完整发布检查清单见：`DEPLOYMENT.md`

### Zeabur 快速上新（推荐线上）

```bash
# 一次部署（会自动创建项目/服务）
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service temu-image-gen

# 绑定你自己的域名（可选）
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service temu-image-gen --domain your.domain.com

# 后续最快更新（推荐固定使用 service-id）
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service-id 你的service_id
```

说明：`scripts/deploy-zeabur.sh` 默认会先做“瘦身上下文”再上传，明显降低上新耗时。

> 地区限制提示：若出图出现 `400 FAILED_PRECONDITION` 且包含 `User location is not supported`，通常是部署节点出口 IP 地区不在 Gemini 出图可用范围，请改为受支持地区节点（如 US/JP/SG）或改用 Vertex AI 区域端点。

### Zeabur 免重复填写推荐配置

在服务环境变量中设置以下固定值，重部署后会自动注入，无需手动重复填密码/API Key：

```bash
SYSTEM_API_KEYS_FIXED=AIza_key_1,AIza_key_2
# 如使用 Vertex AI Express Key（AQ...），建议同时加上：
GOOGLE_GENAI_USE_VERTEXAI=true
SYSTEM_API_KEYS_SYNC_MODE=if_empty
ADMIN_PASSWORD_FIXED=你的管理员密码
USER_PASSWORD_FIXED=你的用户密码
ALLOW_PASSWORDLESS_USER_LOGIN=true
```

`SYSTEM_API_KEYS_SYNC_MODE` 说明：
- `if_empty`：仅当系统 Key 为空时注入（推荐）
- `merge`：合并到现有 Key 池
- `replace`：每次重启都覆盖为固定 Key（最强一致）

说明：
- `ALLOW_PASSWORDLESS_USER_LOGIN=true` 后，普通用户可直接进入业务页面。
- 管理后台依然只允许管理员密码进入。
- 建议把这些值放在 Zeabur 环境变量，不要写死到仓库代码。

### Debian 12+ Docker 部署（推荐）

```bash
chmod +x scripts/deploy-debian.sh
./scripts/deploy-debian.sh install
```

### 本地开发

```bash
pip install -r requirements.txt
streamlit run app.py
```

### macOS 本地运行示例

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=你的APIKey
streamlit run app.py
```

## 🎯 使用流程

### 智能组图
1. 上传商品图片 → AI分析
2. 选择图片类型 (主图/卖点/场景等)
3. 编辑图需文案
4. 合规检测
5. 生成图片 → 查看结果 → 下载ZIP

### 快速出图
1. 上传图片 + 输入商品名
2. 选择图片类型
3. 一键生成 → 下载

### 标题生成
- 支持纯文字输入
- 支持图片分析
- 支持图片+文字混合
- 输出中英双语标题

### 图片翻译
1. 上传电商图片
2. 选择源语言与目标语言
3. 选择仅文本翻译 / 翻译出图 / 两者皆有
4. 选择尺寸策略（保留原比例 / 强制 1:1 / 自定义比例）
5. 选择合规词策略（保留 / 追加 / 模板）并查看生效合规词
6. 译后图速览 → 集中勾选下载 → 一键下载 ZIP

### 图片翻译（当前版本说明）
- 默认下载对象为译后图（PNG）
- 不再要求下载原图，也不再强制做原图/译后对照导出
- 不再在结果页切换 PNG/JPG，避免大批量场景下反复重载
- 需要核对时可在“单图详情”查看对应文本与合规命中
- 新增“极速文本链路（OCR+翻译合并）”选项，批量文本翻译可明显提速
- 英文目标可启用“强制英文规范输出（Amazon/Team）”，文本与出图会自动做英文残留校验并重试
- 新增“清理中文覆盖文案/角标（默认开启）”，会优先清理非产品主体的中文叠字与角标覆盖文本（品牌/商标 Logo 保留）
- 新增“后台排队（可并发）”执行方式，可连续提交多个翻译任务并在后台任务面板加载结果
- 管理后台的“后台并发任务上限”会直接控制后台同时运行任务数（超出后自动排队）
- 页底新增“今日已出图 X 张”实时统计

### 速度建议（翻译模块）
- 固定使用：`🍌 Nano Banana 2`（图片生成与翻译统一）
- 推理级别：优先 `minimal`（更快）；对复杂图再改 `high`
- 大批量时在管理后台把“后台并发任务上限”与“文本并发线程数”先设为 `2~3`
- 参考 Google 官方图片生成文档进行参数约束与重试策略优化：[Gemini Image Generation](https://ai.google.dev/gemini-api/docs/image-generation)

## 🤖 模型支持

| 模型 | 分辨率 | 参考图 | 推理级别 |
|------|--------|--------|----------|
| 🍌 Nano Banana 2 | 1K | 5张 | minimal, high |

## 📝 标题模板示例

### 默认TEMU优化模板
```
ROLE You are an ecommerce title optimization expert...
TASK Generate exactly three product titles with English and Chinese...
OUTPUT FORMAT (exactly 6 lines):
[English Title 1 - 180-250 chars]
[中文标题1]
...
```

### 图片智能分析模板
```
Analyze the product image(s) and generate 3 bilingual titles...
English: 180-250 characters
Chinese: accurate natural translation
```

## 👥 作者信息

- **核心作者**: 企鹅 & 小明
- **商业订阅**: 企鹅 & Jerry

---

© 2024 All Rights Reserved.
