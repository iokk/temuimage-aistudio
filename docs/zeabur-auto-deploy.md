# Zeabur Auto-Deploy Quickstart

`rebuild-v1.0.0` 的正式部署入口是仓库根目录的 `template.yaml`。

## 结论先说

- Zeabur **不会**因为你连接了 GitHub 仓库，就自动执行这个仓库里的 `template.yaml`
- 想做到最接近“一拉即用”，正式路径应该是：
  1. 用 `template.yaml` 创建 Zeabur Template
  2. 用这个 Template / Deploy Button 创建项目
  3. 只手动填写域名和 secrets
  4. 后续代码 push 走 Zeabur 的 Git 自动 redeploy

## 正式入口

- 模板文件：`template.yaml`
- API Dockerfile：`apps/api/Dockerfile`
- Worker Dockerfile：`apps/worker/Dockerfile`
- Web Dockerfile：`apps/web/Dockerfile`

不要使用仓库根目录 `Dockerfile` 来部署 `rebuild-v1.0.0`。那个文件仍然对应归档中的 legacy Streamlit 应用。

## 最少人工步骤

### 1. 生成模板变量

```bash
python3 scripts/generate_zeabur_env.py --web-domain studio.example.com --api-domain api.example.com --casdoor-issuer https://casdoor.example.com --casdoor-client-id your-client-id --casdoor-client-secret your-client-secret --admin-emails owner@example.com --allowed-domains example.com
```

脚本会输出两部分：

- `# Zeabur template variables`：直接用于创建/更新 Zeabur Template 时填写
- `# Service env blocks`：用于 Zeabur 控制台核对，或 raw Git fallback 时手动粘贴

如果你只想要模板变量：

```bash
python3 scripts/generate_zeabur_env.py --format template
```

如果你只想要服务级 env：

```bash
python3 scripts/generate_zeabur_env.py --format services
```

### 2. 在 Zeabur 创建模板 / Deploy Button

- 使用 `template.yaml` 作为正式模板
- 如果已经发布成 Zeabur Template，可再生成 Deploy Button

#### 推荐发布流程（官方支持的最短路径）

1. 先在本地安装并登录 Zeabur CLI
2. 用 `template deploy` 验证 `template.yaml` 可以正常部署
3. 用 `template create` 发布模板
4. 到 Zeabur Dashboard 的 Template 页面生成 Deploy Button

```bash
npx zeabur@latest template deploy -f template.yaml
```

上面这一步的目的不是长期运维，而是确认：

- 模板变量能被正确识别
- `web` / `api` / `worker` / `postgresql` / `redis` 的拓扑没写错
- `apps/api/Dockerfile`、`apps/worker/Dockerfile`、`apps/web/Dockerfile` 路径有效

验证通过后再发布：

```bash
npx zeabur@latest template create -f template.yaml
```

发布成功后，Zeabur 会给出一个模板地址，形如：

```text
https://zeabur.com/templates/XXXXXX
```

#### Deploy Button 生成方式

Zeabur 的 Deploy Button 不是直接从 GitHub repo 生成的，而是**从已发布模板生成**。

正式步骤：

1. 打开 Zeabur Dashboard
2. 进入 `Account -> Template`
3. 选择刚发布的模板
4. 点击 `Share`
5. 复制 HTML 或 Markdown 形式的 Deploy Button

如果后续你更新了 `template.yaml`，需要重新发布/更新模板；**已存在的项目不会因为模板更新而自动变更**。

如果要更新已发布模板：

```bash
npx zeabur@latest template update -c <template-code> -f template.yaml
```

其中 `<template-code>` 是模板 URL 里的短码。

#### 哪些步骤仍然需要人工完成

- GitHub 授权 / repo 连接
- 首次发布模板
- 从 Dashboard 复制 Deploy Button
- 填写域名和 secrets
- 模板更新后手动决定是否重新部署已有项目

### 3. 部署后验收

```bash
API_BASE_URL=https://api.example.com WEB_BASE_URL=https://studio.example.com API_BEARER_TOKEN=<casdoor-admin-token> ./scripts/zeabur_rebuild_release.sh
```

## 哪些能自动化，哪些不能

### 已经能由仓库自动化的部分

- 多服务拓扑：`web` / `api` / `worker` / `postgresql` / `redis`
- Dockerfile 路径
- API / Web 动态 `PORT` 兼容
- `DATABASE_URL` / `REDIS_URL` 注入
- `JOB_STORE_BACKEND=database`
- `ASYNC_JOB_BACKEND=celery`
- `AUTO_BOOTSTRAP_DB=true` on API
- 后续 Git push 触发 redeploy

### 仍然需要平台侧手动输入的部分

- GitHub 授权 / 仓库连接
- 域名
- `NEXTAUTH_SECRET`
- `SYSTEM_ENCRYPTION_KEY`
- Casdoor 相关 secrets
- 团队邮箱白名单配置

## 推荐做法

- 把 `template.yaml` 当成唯一正式入口
- 把 `scripts/generate_zeabur_env.py` 的输出当成唯一填写源
- 先跑一次 `npx zeabur@latest template deploy -f template.yaml` 再发布模板
- 部署完成后统一跑 `scripts/zeabur_rebuild_release.sh`
- 后续更新直接 push 到连接的分支，让 Zeabur 自动 redeploy
