from __future__ import annotations


def build_login_tab_labels(runtime_mode: str):
    return ["👤 个人模式", "🛠️ 团队/管理员"]


def build_settings_sections():
    return {
        "personal": {
            "gemini": {
                "title": "我的 Gemini 凭据",
                "desc": "使用自己的 Google 官方 Gemini / Vertex Key。",
                "badge": "个人",
            },
            "relay": {
                "title": "我的中转站凭据",
                "desc": "使用自己的中转站 URL / Key / 图片模型。",
                "badge": "个人",
            },
        },
        "system": {
            "gemini": {
                "title": "系统 Gemini 配置",
                "desc": "管理员统一维护的 Gemini / Vertex Key。",
                "badge": "系统",
            },
            "relay": {
                "title": "系统中转站配置",
                "desc": "管理员统一维护的中转站 URL / Key / 模型。",
                "badge": "系统",
            },
        },
    }


def build_recommended_provider_templates():
    return [
        {
            "title": "推荐模板：中转站主力模式",
            "summary": "图片生成走中转站，分析/标题模型走 relay 分析模型，适合当前管理员工具模式。",
        },
        {
            "title": "推荐模板：官方 Gemini 模式",
            "summary": "标题优化和图片翻译更稳定，适合使用自己的官方 Gemini Key。",
        },
    ]
