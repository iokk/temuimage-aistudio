# 维护与故障规范

## 日常检查

```bash
python3 -m unittest discover -v
docker compose config --quiet
git diff --check
```

查看 `data/logs/app.log`、`data/tasks.sqlite3` 和 `data/projects/`，先确认任务状态，再判断是上游、网络还是本地文件问题。

## 故障分类

- `queued/running`：调度或上游处理中，页面只显示摘要；不要通过刷新页面重跑。
- `error/partial`：读取任务错误和逐项结果，仅重试失败项。
- 超时：先看 provider 响应时间、代理和 `TASK_RUNNER_LEASE_SECONDS`，确认上游冷却后再重试。
- 结果缺失：检查项目目录、磁盘空间和日志，不直接修改 SQLite 文档。

## 备份与回滚

升级前备份整个 `data/`（包括 SQLite 的 WAL/SHM）。回滚时恢复数据目录并切回已验证标签；禁止提交 `.env`、API Key、运行数据和 `.superpowers/`。

## AI 接手规则

先读 `README.md`、`ARCHITECTURE.md`、`DESIGN.md`、本文件和当前验收记录；改动前写失败测试，改动后运行专项与全量测试。日志、文档和错误信息必须脱敏，禁止输出凭据或执行未经授权的真实付费图片调用。
