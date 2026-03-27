# 推荐配置模板清单

这份文档给出 3 套可直接照抄的常用配置方案，方便你部署后快速落地。

## 模板 A：中转站主力模式（推荐）

适合当前管理员工具模式，也是最推荐的默认方案。

### 适用场景

- 主要依赖中转站
- 想让 `1/2/4` 优先走 relay-first
- 标题、分析继续用 relay 分析模型

### 系统配置

```text
默认出图引擎: 中转站
系统中转站 API 地址: https://newapi.aisonnet.org/v1
系统中转站默认图片模型: seedream-5.0
系统中转站分析/标题模型: gemini-3.1-flash-image-preview
```

### 推荐用途

- `1 批量出图`: relay-first
- `2 快速出图`: relay-first
- `3 标题优化`: relay 分析模型
- `4 图片翻译`: `seedream-5.0` 优先

### 说明

- 这是当前最均衡、最省心的一套
- 如果某个 relay 模型不支持某项任务，页面会明确提示

---

## 模板 B：官方 Gemini 模式

适合更重视稳定性，且你有官方 Gemini / Vertex Key 的场景。

### 系统配置

```text
默认出图引擎: Gemini
系统 Gemini Key: 已配置
TITLE_TEXT_MODEL: gemini-3.1-pro
```

### 推荐用途

- `3 标题优化`: 最稳
- `4 图片翻译`: 最稳
- `1/2`: 适合不依赖中转站时直接使用

### 说明

- 如果你的官方 Key 配额充足，这套稳定性最好
- 成本和速率限制取决于官方链路

---

## 模板 C：混合模式

适合你既要中转站主力出图，又想保留 Gemini 作兜底。

### 系统配置

```text
默认出图引擎: 中转站
系统中转站 API 地址: https://newapi.aisonnet.org/v1
系统中转站默认图片模型: seedream-5.0
系统中转站分析/标题模型: gemini-3.1-flash-image-preview
系统 Gemini Key: 已配置
TITLE_TEXT_MODEL: gemini-3.1-pro
```

### 推荐用途

- `1/2`: 走 relay-first
- `3`: 可按需要切个人 Gemini / 系统 Gemini
- `4`: relay 支持时走 relay，不支持时仍有 Gemini 兜底

### 说明

- 这是功能覆盖最完整的一套
- 也最适合你现在这种“管理员工具系统 + 中转站主力 + 官方兜底”的形态

---

## 个人凭据建议

如果用户自己要用凭据，建议只开放两种明确选择：

### 个人 Gemini

```text
我的 Gemini / Vertex Key
```

适合：

- 自己测试标题优化
- 自己做图片翻译
- 不想占用系统额度

### 个人中转站

```text
我的中转站 URL / Key / 模型
```

适合：

- 自己测试中转站模型
- 不想影响系统中转站配置

---

## 当前推荐默认值

如果你不想思考，先直接用这套：

```text
默认出图引擎: 中转站
系统中转站 API 地址: https://newapi.aisonnet.org/v1
系统中转站默认图片模型: seedream-5.0
系统中转站分析/标题模型: gemini-3.1-flash-image-preview
TITLE_TEXT_MODEL: gemini-3.1-pro
```

这套最适合你当前版本。
