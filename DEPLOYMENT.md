# TEMU 部署与发布检查清单

## 1) 本地发布前检查

```bash
python3 -m py_compile app.py
bash -n scripts/deploy-quick.sh
bash -n scripts/deploy-debian.sh
bash -n deploy.sh
```

## 2) Docker 部署（推荐）

```bash
./scripts/deploy-quick.sh up
./scripts/deploy-quick.sh status
```

健康检查地址：

`http://localhost:8501/_stcore/health`

## 2.1) Zeabur 快速部署（更快上新）

```bash
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service temu-image-gen
```

后续发布（最快）建议固定 `service-id`：

```bash
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service-id 你的service_id
```

可选绑定域名：

```bash
ZEABUR_TOKEN=你的token ./scripts/deploy-zeabur.sh --project temu-v15 --service temu-image-gen --domain your.domain.com
```

说明：脚本默认会使用“瘦身上传上下文”，减少无关文件上传，提升部署速度。

### 2.2) Zeabur 固定值注入（免重复填写）

在 Zeabur 服务环境变量添加：

```bash
SYSTEM_API_KEYS_FIXED=AIza_key_1,AIza_key_2
# 如使用 Vertex AI Express Key（AQ...），建议同时加上：
GOOGLE_GENAI_USE_VERTEXAI=true
SYSTEM_API_KEYS_SYNC_MODE=if_empty
ADMIN_PASSWORD_FIXED=你的管理员密码
USER_PASSWORD_FIXED=你的用户密码
ALLOW_PASSWORDLESS_USER_LOGIN=true
```

同步策略说明：
- `if_empty`：仅 Key 池为空时注入（推荐）
- `merge`：固定 Key 合并到现有池
- `replace`：每次重启覆盖 Key 池

## 3) 常见问题

- **启动后无法翻译**：检查 `.env` 是否配置 `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`
- **每次重部署都要重填密码/API Key**：配置 `ADMIN_PASSWORD_FIXED` / `USER_PASSWORD_FIXED` / `SYSTEM_API_KEYS_FIXED`
- **文本翻译慢**：在管理后台开启“极速文本链路”，并将“文本并发线程数”调到 `2~4`
- **图片翻译慢**：优先使用 `⚡ Nano Banana Flash`，必要时降低分辨率到 `1K`
- **批量下载卡顿**：结果页已改为译后图 ZIP 按需缓存，如仍慢请减少单批数量
- **出图报错 `400 FAILED_PRECONDITION User location is not supported`**：优先改用 Vertex AI Express / Vertex AI 区域端点；若仍走 Gemini API，请切换到受支持地区节点（如 US/JP/SG）。

## 4) 一次可复用的发布流程

```bash
# 1. 语法检查
python3 -m py_compile app.py

# 2. 启动容器
./scripts/deploy-quick.sh up

# 3. 观察日志
./scripts/deploy-quick.sh logs

# 4. 版本更新后滚动更新
./scripts/deploy-quick.sh update
```

## 5) 能否直接推送并部署？

可以。建议固定执行：

1. 先跑“本地发布前检查”
2. 再执行 `./scripts/deploy-quick.sh update`
3. 检查 `status` 与健康检查接口

只要上述 3 步通过，就可以稳定复用这套推送与部署流程。
