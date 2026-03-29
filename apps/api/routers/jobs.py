from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import HTTPException
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
def jobs_list(principal: Principal = Depends(get_current_principal)):
    jobs = job_repository.list_jobs(
        owner_id=principal.user_id,
        include_all=principal.is_admin,
    )
    backend_meta = job_repository.get_backend_meta()
    async_meta = get_async_backend_meta()
    return {
        "items": jobs,
        "pending_count": job_repository.count_pending_jobs(
            owner_id=principal.user_id,
            include_all=principal.is_admin,
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
    job = job_repository.create_job(
        task_type=payload.task_type,
        summary=payload.summary,
        status=payload.status,
        owner_id=principal.user_id,
        payload={
            **payload.payload,
            "ownerId": principal.user_id,
            "ownerEmail": principal.email,
            "ownerSubject": principal.subject,
        },
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
    job = job_repository.create_job(
        task_type=payload.task_type,
        summary=payload.summary,
        status="queued",
        owner_id=principal.user_id,
        payload={
            **payload.payload,
            "ownerId": principal.user_id,
            "ownerEmail": principal.email,
            "ownerSubject": principal.subject,
        },
        result=payload.result,
    )
    execution_backend = dispatch_preview_job(
        job["id"],
        payload.task_type,
        payload.payload,
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
