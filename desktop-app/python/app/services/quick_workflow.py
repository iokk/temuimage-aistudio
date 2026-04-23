from pathlib import Path
import threading
import uuid

from app.db.connection import create_connection
from app.repositories.projects import (
    add_project_file,
    create_project,
    get_project,
    update_project_status,
)
from app.repositories.providers import get_provider
from app.repositories.tasks import add_task_event, create_task, update_task
from app.services.quick_generation import QuickGenerationError, QuickGenerator


def create_quick_workflow(
    app,
    *,
    provider_id: str,
    api_key: str,
    image_paths: list[str],
    product_name: str,
    product_detail: str,
    output_language: str,
    aspect_ratio: str,
    image_model: str,
    quick_mode: str,
    image_count: int,
) -> dict:
    runtime = app.state.runtime
    connection = create_connection(runtime.db_path)
    try:
        provider = get_provider(connection, provider_id)
        if not provider:
            raise QuickGenerationError("Provider 不存在。")

        artifact_dir = Path(runtime.files_dir) / "projects" / f"quick-{uuid.uuid4().hex[:12]}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        project = create_project(
            connection,
            project_type="quick_generate",
            summary=f"快速出图 · {product_name} · {image_count}张",
            status="queued",
            provider_id=provider_id,
            title_language="",
            image_language=output_language,
            artifact_dir=str(artifact_dir),
        )
        task = create_task(
            connection,
            task_type="quick_generate",
            status="queued",
            project_id=project["id"],
            provider_id=provider_id,
            payload={
                "image_paths": image_paths,
                "product_name": product_name,
                "product_detail": product_detail,
                "output_language": output_language,
                "aspect_ratio": aspect_ratio,
                "image_model": image_model,
                "quick_mode": quick_mode,
                "image_count": image_count,
            },
            progress_total=image_count,
            progress_done=0,
            current_step="queued",
        )
        add_task_event(
            connection,
            task_id=task["id"],
            level="info",
            event_type="queued",
            message="快速出图任务已进入队列。",
            detail={"image_count": image_count, "mode": quick_mode},
        )
    finally:
        connection.close()

    thread = threading.Thread(
        target=run_quick_task,
        args=(
            app,
            task["id"],
            project["id"],
            provider_id,
            api_key,
            image_paths,
            product_name,
            product_detail,
            output_language,
            aspect_ratio,
            image_model,
            quick_mode,
            image_count,
        ),
        daemon=True,
    )
    app.state.task_threads[task["id"]] = thread
    thread.start()
    return {"task_id": task["id"], "project_id": project["id"], "status": task["status"]}


def run_quick_task(
    app,
    task_id: str,
    project_id: str,
    provider_id: str,
    api_key: str,
    image_paths: list[str],
    product_name: str,
    product_detail: str,
    output_language: str,
    aspect_ratio: str,
    image_model: str,
    quick_mode: str,
    image_count: int,
) -> None:
    connection = create_connection(app.state.runtime.db_path)
    try:
        provider = get_provider(connection, provider_id)
        update_task(
            connection,
            task_id,
            status="running",
            progress_done=0,
            progress_total=image_count,
            current_step="generating_images",
            started_at=_timestamp(),
            error_message="",
        )
        update_project_status(connection, project_id, status="running", completed=False)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="running",
            message="开始执行快速出图。",
        )

        generator = QuickGenerator(
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

        for index, image_path in enumerate(image_paths):
            source = Path(image_path)
            if not source.exists():
                continue
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

        generated_count = 0
        for index in range(image_count):
            generated = generator.generate_image(
                image_paths=image_paths,
                product_name=product_name,
                product_detail=product_detail,
                quick_mode=quick_mode,
                output_language=output_language,
                aspect_ratio=aspect_ratio,
            )
            output_path = output_dir / f"{index + 1:02d}-{quick_mode}.png"
            generated.save(output_path, format="PNG")
            add_project_file(
                connection,
                project_id=project_id,
                file_role="generated_output",
                file_path=str(output_path),
                mime_type="image/png",
                sort_index=index,
            )
            generated_count += 1
            update_task(
                connection,
                task_id,
                progress_done=generated_count,
                progress_total=image_count,
                current_step=f"generated_{generated_count}",
            )

        update_task(
            connection,
            task_id,
            status="succeeded",
            progress_done=generated_count,
            progress_total=image_count,
            current_step="completed",
            ended_at=_timestamp(),
        )
        update_project_status(connection, project_id, status="succeeded", completed=True)
        add_task_event(
            connection,
            task_id=task_id,
            level="info",
            event_type="succeeded",
            message="快速出图完成并已归档。",
            detail={"image_count": generated_count, "mode": quick_mode},
        )
    except Exception as exc:
        update_task(
            connection,
            task_id,
            status="failed",
            progress_done=0,
            progress_total=image_count,
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
