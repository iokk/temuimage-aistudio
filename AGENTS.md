# AI 开发约束

开始修改前阅读 `README.md`、`ARCHITECTURE.md`、`DESIGN.md`、`DEPLOYMENT.md`、`MAINTENANCE.md` 和 `docs/PROJECT_STATUS.md`。

- 使用 TDD：先写并观察失败测试，再写最小实现。
- 保持 Streamlit + SQLite、任务载荷、状态迁移、owner 隔离和 `data/` 目录兼容。
- 不提交 `.env`、`data/`、日志、密钥或 `.superpowers/`。
- API Key、错误日志和验收输出必须脱敏；未经明确授权不执行真实付费图片请求。
- 完成前运行专项测试、`python3 -m unittest discover -v`、编译检查、部署配置检查和 `git diff --check`。
- 版本发布需更新 `CHANGELOG.md`、验收文档并保持 CNB 分支和标签一致。
