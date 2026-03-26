from __future__ import annotations


def build_feature_catalog():
    return [
        {
            "key": "workspace",
            "nav": "工作台",
            "emoji": "◫",
            "title": "工作台",
            "subtitle": "统一查看系统模式、引擎状态和四个核心功能入口。",
        },
        {
            "key": "combo",
            "nav": "批量出图",
            "emoji": "▦",
            "title": "批量出图",
            "subtitle": "多张参考图、多类型卖点图的标准工作流。",
        },
        {
            "key": "smart",
            "nav": "快速出图",
            "emoji": "⚡",
            "title": "快速出图",
            "subtitle": "更少步骤，适合单批快速生成。",
        },
        {
            "key": "title",
            "nav": "标题优化",
            "emoji": "⌗",
            "title": "标题优化",
            "subtitle": "结合图片和补充信息输出英文标题。",
        },
        {
            "key": "translate",
            "nav": "图片翻译",
            "emoji": "文",
            "title": "图片翻译",
            "subtitle": "提取文字、翻译并生成译后图。",
        },
    ]


def build_admin_mode_notice(has_service_access: bool, team_ready: bool):
    if team_ready:
        return {
            "level": "success",
            "title": "团队模式已启用",
            "body": "注册用户、项目、钱包与管理员后台都已可用。",
        }

    if has_service_access:
        return {
            "level": "info",
            "title": "当前为管理员模式",
            "body": "系统中转站或系统 Gemini 已可直接使用。只有注册用户、钱包、项目等团队功能才需要数据库。",
        }

    return {
        "level": "warning",
        "title": "系统服务尚未初始化",
        "body": "请先配置系统 Gemini Key 或系统中转站，之后即可先用管理员模式运行。",
    }
