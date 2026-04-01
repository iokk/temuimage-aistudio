from __future__ import annotations

import base64
import io
import zipfile

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from apps.api.async_dispatcher import dispatch_preview_job, get_async_backend_meta
from apps.api.core.auth import Principal, get_current_principal
from apps.api.job_repository import job_repository


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    task_type: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=200)
    status: str = Field(default="completed", max_length=50)
    payload: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)


class JobUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)
    result: dict = Field(default_factory=dict)


def _resolve_current_project(principal: Principal) -> dict:
    account_state = job_repository.get_account_team_state(user_id=principal.user_id)
    current_project = dict(account_state.get("current_project") or {})
    if current_project:
        return current_project

    ensure_project_state = getattr(job_repository, "ensure_project_state", None)
    if callable(ensure_project_state):
        recovered_state = ensure_project_state(user_id=principal.user_id) or {}
        recovered_project = (
            recovered_state.get("current_project")
            if isinstance(recovered_state, dict)
            else None
        )
        current_project = dict(recovered_project or {})
        if current_project:
            return current_project

        account_state = job_repository.get_account_team_state(user_id=principal.user_id)
        current_project = dict(account_state.get("current_project") or {})
        if current_project:
            return current_project

    raise HTTPException(status_code=400, detail="Current project is not available")


def _split_job_payload(task_type: str, payload: dict) -> tuple[dict, dict]:
    dispatch_payload = dict(payload or {})
    if task_type not in {
        "image_translate",
        "quick_generation",
        "batch_generation",
        "title_generation",
    }:
        return dispatch_payload, dispatch_payload

    stored_payload = dict(dispatch_payload)
    upload_items = []
    for item in dispatch_payload.get("uploadItems") or []:
        if not isinstance(item, dict):
            continue
        upload_items.append(
            {
                "id": item.get("id"),
                "rawName": item.get("rawName"),
                "mimeType": item.get("mimeType"),
                "sizeBytes": item.get("sizeBytes"),
            }
        )
    if upload_items:
        stored_payload["uploadItems"] = upload_items
        stored_payload["uploadCount"] = len(upload_items)
    return stored_payload, dispatch_payload


def _build_translate_zip(job: dict) -> bytes:
    outputs = job.get("result", {}).get("outputs") or []
    archive = io.BytesIO()
    written = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for index, item in enumerate(outputs):
            if not isinstance(item, dict):
                continue
            artifact_data_url = str(item.get("artifact_data_url") or "").strip()
            if not artifact_data_url.startswith("data:image/"):
                continue
            try:
                _, encoded = artifact_data_url.split(",", 1)
                image_bytes = base64.b64decode(encoded)
            except Exception as exc:  # pragma: no cover - defensive export path
                raise HTTPException(
                    status_code=400, detail=f"Invalid translate artifact: {exc}"
                ) from exc
            filename = str(
                item.get("filename") or f"translated-{index + 1}.png"
            ).strip()
            bundle.writestr(filename, image_bytes)
            written += 1
    if written == 0:
        raise HTTPException(
            status_code=400, detail="No translated image outputs available for export"
        )
    return archive.getvalue()


def _build_outputs_zip(job: dict) -> bytes:
    outputs = job.get("result", {}).get("outputs") or []
    archive = io.BytesIO()
    written = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for index, item in enumerate(outputs):
            if not isinstance(item, dict):
                continue
            artifact_data_url = str(item.get("artifact_data_url") or "").strip()
            if not artifact_data_url.startswith("data:image/"):
                continue
            try:
                _, encoded = artifact_data_url.split(",", 1)
                image_bytes = base64.b64decode(encoded)
            except Exception as exc:  # pragma: no cover - defensive export path
                raise HTTPException(
                    status_code=400, detail=f"Invalid output artifact: {exc}"
                ) from exc
            filename = str(item.get("filename") or f"artifact-{index + 1}.png").strip()
            bundle.writestr(filename, image_bytes)
            written += 1
    if written == 0:
        raise HTTPException(
            status_code=400, detail="No image outputs available for export"
        )
    return archive.getvalue()


@router.get("/meta")
def jobs_meta(_principal: Principal = Depends(get_current_principal)):
    backend_meta = job_repository.get_backend_meta()
    async_meta = get_async_backend_meta()
    return {
        "task_types": [
            "batch_generation",
            "quick_generation",
            "title_generation",
            "image_translate",
        ],
        **backend_meta,
        **async_meta,
    }


@router.get("/list")
def jobs_list(
    project_id: str | None = None,
    principal: Principal = Depends(get_current_principal),
):
    jobs = job_repository.list_jobs(
        owner_id=principal.user_id,
        include_all=principal.is_admin,
        project_id=project_id,
    )
    backend_meta = job_repository.get_backend_meta()
    async_meta = get_async_backend_meta()
    return {
        "items": jobs,
        "pending_count": job_repository.count_pending_jobs(
            owner_id=principal.user_id,
            include_all=principal.is_admin,
            project_id=project_id,
        ),
        "total": len(jobs),
        **backend_meta,
        **async_meta,
    }


@router.post("/submit")
def jobs_submit(
    payload: JobCreateRequest,
    principal: Principal = Depends(get_current_principal),
):
    current_project = _resolve_current_project(principal)
    enriched_payload = {
        **payload.payload,
        "ownerId": principal.user_id,
        "ownerEmail": principal.email,
        "ownerSubject": principal.subject,
        "projectId": current_project.get("project_id"),
        "projectName": current_project.get("project_name"),
        "projectSlug": current_project.get("project_slug"),
    }
    stored_payload, _ = _split_job_payload(payload.task_type, enriched_payload)
    job = job_repository.create_job(
        task_type=payload.task_type,
        summary=payload.summary,
        status=payload.status,
        owner_id=principal.user_id,
        project_id=str(current_project.get("project_id") or "") or None,
        payload=stored_payload,
        result=payload.result,
    )
    return {
        "job": job,
        "pending_count": job_repository.count_pending_jobs(
            owner_id=principal.user_id,
            include_all=principal.is_admin,
        ),
    }


@router.post("/submit-async")
def jobs_submit_async(
    payload: JobCreateRequest,
    principal: Principal = Depends(get_current_principal),
):
    current_project = _resolve_current_project(principal)
    enriched_payload = {
        **payload.payload,
        "ownerId": principal.user_id,
        "ownerEmail": principal.email,
        "ownerSubject": principal.subject,
        "projectId": current_project.get("project_id"),
        "projectName": current_project.get("project_name"),
        "projectSlug": current_project.get("project_slug"),
    }
    stored_payload, dispatch_payload = _split_job_payload(
        payload.task_type, enriched_payload
    )
    job = job_repository.create_job(
        task_type=payload.task_type,
        summary=payload.summary,
        status="queued",
        owner_id=principal.user_id,
        project_id=str(current_project.get("project_id") or "") or None,
        payload=stored_payload,
        result=payload.result,
    )
    execution_backend = dispatch_preview_job(
        job["id"],
        payload.task_type,
        dispatch_payload,
    )
    return {
        "job": job,
        "pending_count": job_repository.count_pending_jobs(
            owner_id=principal.user_id,
            include_all=principal.is_admin,
        ),
        "execution_backend": execution_backend,
    }


@router.get("/{job_id}")
def jobs_detail(
    job_id: str,
    principal: Principal = Depends(get_current_principal),
):
    job = job_repository.get_job(
        job_id,
        owner_id=principal.user_id,
        include_all=principal.is_admin,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.post("/{job_id}/status")
def jobs_update_status(
    job_id: str,
    payload: JobUpdateRequest,
    principal: Principal = Depends(get_current_principal),
):
    job = job_repository.update_job(
        job_id,
        status=payload.status,
        owner_id=principal.user_id,
        include_all=principal.is_admin,
        result=payload.result,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job": job,
        "pending_count": job_repository.count_pending_jobs(
            owner_id=principal.user_id,
            include_all=principal.is_admin,
        ),
    }


@router.get("/{job_id}/translate-export.zip")
def jobs_translate_export_zip(
    job_id: str,
    principal: Principal = Depends(get_current_principal),
):
    job = job_repository.get_job(
        job_id,
        owner_id=principal.user_id,
        include_all=principal.is_admin,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("task_type") != "image_translate":
        raise HTTPException(
            status_code=400, detail="Only translate jobs support ZIP export"
        )
    archive_bytes = _build_translate_zip(job)
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=translate-{job_id}.zip"},
    )


@router.get("/{job_id}/artifacts.zip")
def jobs_export_artifacts_zip(
    job_id: str,
    principal: Principal = Depends(get_current_principal),
):
    job = job_repository.get_job(
        job_id,
        owner_id=principal.user_id,
        include_all=principal.is_admin,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    archive_bytes = _build_outputs_zip(job)
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=job-{job_id}-artifacts.zip"
        },
    )
