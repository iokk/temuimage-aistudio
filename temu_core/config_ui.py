from __future__ import annotations


def build_login_tab_labels(runtime_mode: str):
    labels = ["🔐 我的凭据", "🎫 系统服务"]
    if runtime_mode == "team_mode":
        labels.append("⚙️ 系统配置")
    return labels


def build_settings_sections():
    return {
        "personal": {
            "gemini": {
                "title": "我的 Gemini 凭据",
                "desc": "使用自己的 Google 官方 Gemini / Vertex Key。",
            },
            "relay": {
                "title": "我的中转站凭据",
                "desc": "使用自己的中转站 URL / Key / 图片模型。",
            },
        },
        "system": {
            "gemini": {
                "title": "系统 Gemini 配置",
                "desc": "管理员统一维护的 Gemini / Vertex Key。",
            },
            "relay": {
                "title": "系统中转站配置",
                "desc": "管理员统一维护的中转站 URL / Key / 模型。",
            },
        },
    }
