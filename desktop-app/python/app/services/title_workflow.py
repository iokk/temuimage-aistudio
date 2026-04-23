import json
from pathlib import Path
import threading
import uuid
from typing import Optional

from app.db.connection import create_connection
from app.repositories.projects import add_project_file, create_project, get_project, list_projects, update_project_status
from app.repositories.providers import get_provider
from app.repositories.tasks import add_task_event, create_task, get_task, list_task_events, list_tasks, update_task
from app.services.title_generation import DEFAULT_TEMPLATE_PROMPT, TitleGenerationError, TitleGenerator


def create_title_workflow(
    app,
    provider_id: str,
    api_key: str,
    product_info: str,
    template_prompt: str,
    title_language: str,
    image_paths: list[str],
) -> dict:
    runtime = app.state.runtime
    connection = create_connection(runtime.db_path)
    try:
        provider = get_provider(connection, provider_id)
        if not provider:
            raise TitleGenerationError("Provider 不存在。")

        summary = f"标题任务 · {title_language.upper()}"
        artifact_dir = Path(runtime.files_dir) / "projects" / f"title-{uuid.uuid4().hex[:12]}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        project = create_project(
            connection,
            project_type="title_generate",
            summary=summary,
            status="queued",
            provider_id=provider_id,
            title_language=title_language,
            image_language="",
            artifact_dir=str(artifact_dir),
        )
        task = create_task(
            connection,
            task_type="title_generate",
            status="queued",
            project_id=project["id"],
            provider_id=provider_id,
            payload={
                "product_info": product_info,
                "title_language": title_language,
                "template_prompt": template_prompt or DEFAULT_TEMPLATE_PROMPT,
                "image_paths": image_paths,
            },
            progress_total=1,
            progress_done=0,
            current_step="queued",
        )
        add_task_event(
            connection,
            task_id=task["id"],
            level="info",
            event_type="queued",
            message="标题生成任务已进入队列。",
        )
    finally:
        connection.close()

    thread = threading.Thread(
        target=run_title_task,
        args=(
            app,
            task["id"],
            project["id"],
            provider_id,
            api_key,
            template_prompt,
            product_info,
            title_language,
            image_paths,
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


def run_title_task(
    app,
    task_id: str,
    project_id: str,
    provider_id: str,
    api_key: str,
    template_prompt: str,
    product_info: str,
    title_language: str,
    image_paths: list[str],
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
            progress_total=1,
            current_step="generating_titles",
            started_at=_timestamp(),
            error_message="",
        )
        update_project_status(connection, project_id, status="running", completed=False)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="running",
            message="开始生成标题。",
        )

        generator = TitleGenerator(
            api_key=api_key,
            title_model=provider["title_model"] if provider else "",
            vision_model=provider["vision_model"] if provider else "",
            base_url=provider["base_url"] if provider else "",
        )
        project = get_project(connection, project_id)
        artifact_dir = Path(project["artifact_dir"])
        export_dir = artifact_dir / "exports"
        input_dir = artifact_dir / "inputs"
        meta_dir = artifact_dir / "meta"
        input_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)

        for index, image_path in enumerate(image_paths):
            source = Path(image_path)
            if not source.exists():
                continue
            target = input_dir / f"{index + 1:02d}-{source.name}"
            if not target.exists():
                target.write_bytes(source.read_bytes())
            add_project_file(
                connection,
                project_id=project_id,
                file_role="input_image",
                file_path=str(target),
                mime_type="image/png",
                sort_index=index,
            )

        if image_paths:
            result = generator.generate_titles_from_images(
                image_paths=image_paths,
                product_info=product_info,
                template_prompt=template_prompt or DEFAULT_TEMPLATE_PROMPT,
                target_language=title_language,
            )
        else:
            result = generator.generate_titles(
                product_info=product_info,
                template_prompt=template_prompt or DEFAULT_TEMPLATE_PROMPT,
                target_language=title_language,
            )
        if not result.success:
            raise TitleGenerationError(result.error_message or "标题生成失败。")

        titles_path = export_dir / "titles.txt"
        raw_path = meta_dir / "raw-response.json"
        titles_path.write_text("\n".join(result.titles), encoding="utf-8")
        raw_path.write_text(
            json.dumps({"titles": result.titles, "raw_text": result.raw_text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        add_project_file(
            connection,
            project_id=project_id,
            file_role="title_output",
            file_path=str(titles_path),
            mime_type="text/plain",
        )
        add_project_file(
            connection,
            project_id=project_id,
            file_role="metadata",
            file_path=str(raw_path),
            mime_type="application/json",
            sort_index=1,
        )

        update_task(
            connection,
            task_id,
            status="succeeded",
            progress_done=1,
            progress_total=1,
            current_step="completed",
            ended_at=_timestamp(),
        )
        update_project_status(connection, project_id, status="succeeded", completed=True)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="succeeded",
            message="标题生成完成并已归档。",
            detail={"titles": result.titles, "image_count": len(image_paths)},
        )
    except Exception as exc:
        update_task(
            connection,
            task_id,
            status="failed",
            progress_done=0,
            progress_total=1,
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


def get_project_snapshot(app, project_id: str) -> Optional[dict]:
    connection = create_connection(app.state.runtime.db_path)
    try:
        return get_project(connection, project_id)
    finally:
        connection.close()
