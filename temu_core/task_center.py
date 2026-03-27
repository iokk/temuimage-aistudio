from __future__ import annotations


TASK_TYPE_META = {
    "combo_generation": {
        "title": "批量出图",
        "page": "批量出图",
        "icon": "▥",
    },
    "smart_generation": {
        "title": "快速出图",
        "page": "快速出图",
        "icon": "⇢",
    },
    "image_translate": {
        "title": "图片翻译",
        "page": "图片翻译",
        "icon": "⇄",
    },
}


def build_task_type_meta(task_type: str):
    return TASK_TYPE_META.get(
        task_type,
        {"title": "任务", "page": "工作台", "icon": "●"},
    )


def count_pending_tasks(tasks: list) -> int:
    return sum(1 for item in tasks if item.get("status") in ("queued", "running"))


def build_task_badge(pending_count: int):
    count = max(int(pending_count or 0), 0)
    return {
        "show": count > 0,
        "label": f"● {count}",
    }


def build_task_panel_title(task_count: int) -> str:
    count = max(int(task_count or 0), 0)
    return f"后台任务中心 ({count})"
