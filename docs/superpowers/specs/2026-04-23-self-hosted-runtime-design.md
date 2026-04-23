# 电商出图工作台双运行模式设计

日期：2026-04-23

## 目标

把仓库主线收敛为个人部署版，并在同一代码库中稳定支持两种运行模式：

1. `desktop/mac`
2. `server/web`

## 核心结论

- 主线彻底移除原有 `rebuild` 多服务架构
- 仓库以当前迁移版 Streamlit 应用为核心
- Linux 部署只保留 `self-hosted` 单机部署路径
- 文件能力必须按运行模式分流，不能再默认假设用户电脑文件系统可被服务端直接操作

## 运行模式

通过 `APP_RUNTIME` 控制：

- `desktop`
- `server`

默认策略：

- 本地直接开发默认 `desktop`
- Docker 容器内默认 `server`

## 共用能力

两种模式共用以下系统：

- 模板库
- 提供商设置
- 项目中心
- 任务队列
- 历史索引
- 回收站
- 文件管理诊断
- 智能组图、快速出图、图片翻译、标题生成

## 分流能力

### desktop/mac

- 可打开本地文件夹
- 可选择本地项目保存目录
- Provider 密钥优先进入 macOS Keychain

### server/web

- 只允许浏览器上传与下载
- 结果先保存到服务器项目中心
- 不显示“打开文件夹”
- 不允许把访问者电脑路径当作保存目录
- 不依赖 macOS Keychain

## 数据目录

- `desktop` 默认项目目录：`~/Downloads/电商出图工作台`
- `server` 默认项目目录：`/app/data/projects`

## 仓库策略

- 远端 `main` 改为迁移版主线
- 旧 `rebuild` 主线归档到远端备份分支
- README、部署说明、Docker、Compose、脚本全部改为 self-hosted 单机版口径

## 本轮实施边界

1. 重置仓库工作树为迁移版
2. 删除旧 rebuild 主工作树内容
3. 引入 `APP_RUNTIME`
4. 对文件管理相关 UI 做 desktop/server 分流
5. 更新 README、DEPLOYMENT、Docker、Compose、部署脚本
6. 进行本地编译与 Docker 级验证
