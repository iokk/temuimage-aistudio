from __future__ import annotations


def build_feature_catalog():
    return [
        {
            "key": "workspace",
            "nav": "工作台",
            "emoji": "⬚",
            "title": "工作台",
            "subtitle": "查看当前模式、默认引擎和四个核心功能入口。",
        },
        {
            "key": "combo",
            "nav": "批量出图",
            "emoji": "▥",
            "title": "批量出图",
            "subtitle": "多张参考图、多类型卖点图的标准流程。",
        },
        {
            "key": "smart",
            "nav": "快速出图",
            "emoji": "⇢",
            "title": "快速出图",
            "subtitle": "更少步骤，适合单批快速生成。",
        },
        {
            "key": "title",
            "nav": "标题优化",
            "emoji": "⌘",
            "title": "标题优化",
            "subtitle": "结合图片与补充信息输出英文标题。",
        },
        {
            "key": "translate",
            "nav": "图片翻译",
            "emoji": "⇄",
            "title": "图片翻译",
            "subtitle": "提取文字、翻译并生成译后图片。",
        },
    ]


def build_workspace_actions():
    return [
        {"target": "批量出图", "label": "批量出图"},
        {"target": "快速出图", "label": "快速出图"},
        {"target": "标题优化", "label": "标题优化"},
        {"target": "图片翻译", "label": "图片翻译"},
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
            "body": "系统 Gemini 或系统中转站已可直接使用。团队功能需要数据库时再启用。",
        }

    return {
        "level": "warning",
        "title": "系统服务尚未初始化",
        "body": "请先配置系统 Gemini Key 或系统中转站，之后即可先用管理员模式运行。",
    }


def build_page_sections(page_key: str):
    mapping = {
        "combo": [
            {
                "key": "assets",
                "title": "素材与商品信息",
                "desc": "上传参考图并确认商品基础信息。",
            },
            {
                "key": "types",
                "title": "出图类型与标题",
                "desc": "选择目标图片类型和是否同时生成标题。",
            },
            {
                "key": "brief",
                "title": "图需文案",
                "desc": "检查和编辑中文图需与英文入图文案。",
            },
            {
                "key": "compliance",
                "title": "合规检测",
                "desc": "确认文案风险词与最终可出图状态。",
            },
            {
                "key": "generate",
                "title": "生成与结果",
                "desc": "执行任务并查看批量结果。",
            },
        ],
        "smart": [
            {
                "key": "assets",
                "title": "上传与商品信息",
                "desc": "快速放入商品图和基础信息。",
            },
            {
                "key": "types",
                "title": "类型选择与标题",
                "desc": "选择图片类型并决定是否生成标题。",
            },
            {
                "key": "generate",
                "title": "生成与结果",
                "desc": "直接开始生成并查看结果。",
            },
        ],
    }
    return mapping.get(page_key, [])


def build_result_summary(
    title: str,
    success_count: int,
    total_count: int,
    token_count: int,
    warning_count: int = 0,
    error_count: int = 0,
):
    total = max(int(total_count or 0), 0)
    success = max(int(success_count or 0), 0)
    if total and success == total and error_count == 0:
        state = "success"
    elif success > 0:
        state = "partial"
    elif error_count > 0:
        state = "error"
    else:
        state = "neutral"
    return {
        "title": title,
        "state": state,
        "headline": f"{success} / {total} 成功",
        "token_text": f"{int(token_count or 0):,} tokens",
        "warning_text": f"{int(warning_count or 0)} 条警告",
        "error_text": f"{int(error_count or 0)} 条错误",
    }
