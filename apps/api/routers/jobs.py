from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/meta")
def jobs_meta():
    return {
        "task_types": [
            "batch_generation",
            "quick_generation",
            "title_generation",
            "image_translate",
        ]
    }
