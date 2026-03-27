from __future__ import annotations

from datetime import date


APP_NAME = "小白图 跨境电商出图系统"
APP_EN_NAME = "AI Studio"
APP_COMPANY = "深圳祖尔科技有限公司"
APP_VERSION = "v2026.03.28"
APP_LAST_UPDATED = "最近更新 2026-03-28"
APP_TAGLINE = "批量出图 · 快速出图 · 标题优化 · 图片翻译"


def build_footer_meta():
    today = date.today().isoformat()
    return {
        "company_line": f"{APP_COMPANY}",
        "version_line": f"{today} · {APP_VERSION}",
    }
