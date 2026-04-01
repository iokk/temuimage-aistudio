from __future__ import annotations

from apps.api.task_execution import execute_batch_task
from apps.api.task_execution import execute_quick_task
from apps.api.task_execution import execute_translate_task
from apps.api.task_execution import execute_title_task


def process_task_preview(task_type: str, payload: dict) -> dict:
    if task_type == "title_generation":
        return execute_title_task(payload)

    if task_type == "image_translate":
        return execute_translate_task(payload)

    if task_type == "quick_generation":
        return execute_quick_task(payload)

    if task_type == "batch_generation":
        return execute_batch_task(payload)

    raise ValueError(f"Unsupported task type: {task_type}")
