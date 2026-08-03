# TuLite 架构说明

## 数据流

浏览器/Streamlit 页面负责收集输入、创建任务、查询摘要和执行用户操作；SQLite 是任务状态的唯一真相源；`TaskEngine`/supervisor 独立领取排队任务并调用 provider；结果文件写入 `data/`，项目索引随后归档到项目中心。

```text
UI -> TaskStore(SQLite) -> TaskEngine -> Provider
                         -> Result files(data/) -> Project history
```

## 边界与契约

- 任务生命周期必须遵守 `task_status.py` 的合法迁移，页面刷新不得驱动任务执行。
- `task_store.py` 负责事务、owner 隔离、租约和分页；后台调度不得直接操作 UI 状态。
- provider 适配器必须返回统一结果契约；密钥只能来自加密配置或运行环境。
- 图片列表默认只读取元数据，原图在用户展开预览、下载或导出时读取。

## 扩展方式

新增任务类型时，先定义载荷/结果契约和仓储测试，再注册 `TaskHandler`，最后增加页面入口和验收测试。不要在页面中复制调度、重试或文件清理逻辑。
