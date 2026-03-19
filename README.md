# TEMU AI Studio V1.0.0

TEMU AI Studio 是一个面向电商场景的图片工作台，当前聚焦 4 个核心能力：

- 批量出图
- 快速出图
- 标题优化
- 图片翻译

当前默认图片模型统一为 `Nano Banana 2`，代码层对应模型名为 `gemini-2.5-flash-image`。

## 核心特性

- 默认图片模型锁定为 `Nano Banana 2`
- 支持 `Gemini API Key` 与 `Vertex Express Key`
- 支持英文纯净校验与自动重试
- 支持图片翻译后台任务
- 支持今日出图统计
- 支持 GitHub → Zeabur 拉取部署

## 默认配置

- 图片模型：`gemini-2.5-flash-image`
- 推荐推理级别：`minimal`
- Vertex Express 建议图片低并发
- 默认输出分辨率：`1K`

## API Key 模式

支持两类 Key：

- `AIza...`：Gemini API Key
- `AQ...`：Vertex Express Key

如果使用 `AQ...`，建议同时设置：

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
```

## 中转站模型接入

图片生成页当前支持两类出图入口：

- `Gemini`：默认入口，适合正式出图
- `中转站`：适合接入第三方 OpenAI 兼容图片模型

当前中转站默认接口：

```bash
https://newapi.aisonnet.org/v1
```

已接入模型名：

- `nano-banana-pro-reverse`
- `z-image-turbo`
- `imagine_x_1`
- `hunyuan-image-3`
- `grok-imagine-image`

当前测试状态：

- `imagine_x_1`：不稳定
- `grok-imagine-image`：不稳定
- `z-image-turbo`：当前无通道
- `hunyuan-image-3`：当前无通道
- `nano-banana-pro-reverse`：当前无通道

说明：

- 批量出图、快速出图已支持 `Gemini / 中转站` 二选一
- 图片翻译当前仍固定使用 `Gemini / Vertex`
- 中转站 API Key 支持浏览器本地记忆
- 中转站模型是否真正可出图，仍取决于上游通道实时状态

## 部署方式

### 方式一：GitHub → Zeabur

推荐流程：

1. 代码推送到 GitHub 仓库
2. 在 Zeabur 新建服务并连接仓库
3. 配置环境变量
4. 后续通过 `git push` 自动更新

推荐环境变量：

```bash
SYSTEM_API_KEYS_FIXED=AQ.xxxxx
SYSTEM_API_KEYS_SYNC_MODE=replace
GOOGLE_GENAI_USE_VERTEXAI=true
ADMIN_PASSWORD_FIXED=你的管理员密码
USER_PASSWORD_FIXED=你的用户密码
ALLOW_PASSWORDLESS_USER_LOGIN=true
PORT=8501
```

### 方式二：服务器原生部署

```bash
./scripts/deploy-debian.sh install
```

## 目录说明

- `app.py`：主应用
- `scripts/deploy-zeabur.sh`：Zeabur 发布脚本
- `scripts/deploy-debian.sh`：服务器部署脚本
- `docker-compose.yml`：本地 / 服务器容器部署
- `.env.example`：环境变量示例

## 运行前检查

```bash
python3 -m py_compile app.py
```

## 当前仓库

GitHub 仓库：

`https://github.com/iokk/temu-ai-studio-v1`
