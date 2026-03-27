from __future__ import annotations


def build_core_function_nav():
    return [
        {"key": "combo", "label": "批量出图"},
        {"key": "smart", "label": "快速出图"},
        {"key": "title", "label": "标题优化"},
        {"key": "translate", "label": "图片翻译"},
    ]


def build_page_switch_targets(current_page: str):
    targets = [{"key": "workspace", "label": "返回首页"}]
    for item in build_core_function_nav():
        if item["label"] != current_page:
            targets.append(item)
    return targets


def get_thumbnail_sizes():
    return {
        "combo": 88,
        "smart": 84,
        "title": 72,
        "translate": 88,
    }


def build_task_indicator(task_count: int):
    count = max(int(task_count or 0), 0)
    return {
        "show": count > 0,
        "label": f"● 后台任务 {count}",
    }
