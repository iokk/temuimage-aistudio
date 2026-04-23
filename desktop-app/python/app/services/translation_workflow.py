from pathlib import Path
import threading
import uuid
from typing import Optional

from app.db.connection import create_connection
from app.repositories.projects import (
    add_project_file,
    create_project,
    get_project,
    list_projects,
    update_project_status,
)
from app.repositories.providers import get_provider
from app.repositories.tasks import (
    add_task_event,
    create_task,
    get_task,
    list_task_events,
    list_tasks,
    update_task,
)
from app.services.translation_generation import ImageTranslationError, ImageTranslator


def create_translation_workflow(
    app,
    provider_id: str,
    api_key: str,
    image_paths: list[str],
    image_language: str,
    compliance_mode: str,
    aspect_ratio: str,
    image_model: str,
) -> dict:
    runtime = app.state.runtime
    connection = create_connection(runtime.db_path)
    try:
        provider = get_provider(connection, provider_id)
        if not provider:
            raise ImageTranslationError("Provider 不存在。")

        artifact_dir = Path(runtime.files_dir) / "projects" / f"translate-{uuid.uuid4().hex[:12]}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        project = create_project(
            connection,
            project_type="image_translate",
            summary=f"翻译任务 · {image_language.upper()}",
            status="queued",
            provider_id=provider_id,
            title_language="",
            image_language=image_language,
            artifact_dir=str(artifact_dir),
        )
        task = create_task(
            connection,
            task_type="image_translate",
            status="queued",
            project_id=project["id"],
            provider_id=provider_id,
            payload={
                "image_paths": image_paths,
                "image_language": image_language,
                "compliance_mode": compliance_mode,
                "aspect_ratio": aspect_ratio,
                "image_model": image_model,
            },
            progress_total=len(image_paths),
            progress_done=0,
            current_step="queued",
        )
        add_task_event(
            connection,
            task_id=task["id"],
            level="info",
            event_type="queued",
            message="图片翻译任务已进入队列。",
            detail={"image_count": len(image_paths)},
        )
    finally:
        connection.close()

    thread = threading.Thread(
        target=run_translation_task,
        args=(
            app,
            task["id"],
            project["id"],
            provider_id,
            api_key,
            image_paths,
            image_language,
            compliance_mode,
            aspect_ratio,
            image_model,
        ),
        daemon=True,
    )
    app.state.task_threads[task["id"]] = thread
    thread.start()
    return {
        "task_id": task["id"],
        "project_id": project["id"],
        "status": task["status"],
    }


def run_translation_task(
    app,
    task_id: str,
    project_id: str,
    provider_id: str,
    api_key: str,
    image_paths: list[str],
    image_language: str,
    compliance_mode: str,
    aspect_ratio: str,
    image_model: str,
) -> None:
    runtime = app.state.runtime
    connection = create_connection(runtime.db_path)
    try:
        provider = get_provider(connection, provider_id)
        update_task(
            connection,
            task_id,
            status="running",
            progress_done=0,
            progress_total=len(image_paths),
            current_step="translating_images",
            started_at=_timestamp(),
            error_message="",
        )
        update_project_status(connection, project_id, status="running", completed=False)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="running",
            message="开始执行图片翻译。",
        )

        translator = ImageTranslator(
            api_key=api_key,
            model=image_model or (provider["image_model"] if provider else ""),
            base_url=provider["base_url"] if provider else "",
        )
        project = get_project(connection, project_id)
        artifact_dir = Path(project["artifact_dir"])
        input_dir = artifact_dir / "inputs"
        output_dir = artifact_dir / "outputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        translated_count = 0
        for index, image_path in enumerate(image_paths):
            source = Path(image_path)
            if source.exists():
                archived_input = input_dir / f"{index + 1:02d}-{source.name}"
                if not archived_input.exists():
                    archived_input.write_bytes(source.read_bytes())
                add_project_file(
                    connection,
                    project_id=project_id,
                    file_role="input_image",
                    file_path=str(archived_input),
                    mime_type="image/png",
                    sort_index=index,
                )

            translated = translator.translate_image(
                image_path=image_path,
                target_language=image_language,
                compliance_mode=compliance_mode,
                aspect_ratio=aspect_ratio,
            )
            output_path = output_dir / f"{index + 1:02d}-translated.png"
            translated.save(output_path, format="PNG")
            add_project_file(
                connection,
                project_id=project_id,
                file_role="translated_output",
                file_path=str(output_path),
                mime_type="image/png",
                sort_index=index,
            )
            translated_count += 1
            update_task(
                connection,
                task_id,
                progress_done=translated_count,
                progress_total=len(image_paths),
                current_step=f"translated_{translated_count}",
            )

        update_task(
            connection,
            task_id,
            status="succeeded",
            progress_done=translated_count,
            progress_total=len(image_paths),
            current_step="completed",
            ended_at=_timestamp(),
        )
        update_project_status(connection, project_id, status="succeeded", completed=True)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="succeeded",
            message="图片翻译完成并已归档。",
            detail={"image_count": translated_count},
        )
    except Exception as exc:
        update_task(
            connection,
            task_id,
            status="failed",
            progress_done=0,
            progress_total=len(image_paths),
            current_step="failed",
            error_message=str(exc),
            ended_at=_timestamp(),
        )
        update_project_status(connection, project_id, status="failed", completed=True)
        add_task_event(
            connection,
            task_id=task_id,
            level="error",
            event_type="failed",
            message=str(exc),
        )
    finally:
        connection.close()
        app.state.task_threads.pop(task_id, None)


def _timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def get_task_snapshot(app, task_id: str) -> Optional[dict]:
    connection = create_connection(app.state.runtime.db_path)
    try:
        return get_task(connection, task_id)
    finally:
        connection.close()


def list_task_snapshots(app) -> list[dict]:
    connection = create_connection(app.state.runtime.db_path)
    try:
        return list_tasks(connection)
    finally:
        connection.close()


def list_task_event_snapshots(app, task_id: str) -> list[dict]:
    connection = create_connection(app.state.runtime.db_path)
    try:
        return list_task_events(connection, task_id)
    finally:
        connection.close()


def list_project_snapshots(app) -> list[dict]:
    connection = create_connection(app.state.runtime.db_path)
    try:
        return list_projects(connection)
    finally:
        connection.close()

