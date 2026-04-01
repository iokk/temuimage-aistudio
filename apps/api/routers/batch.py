from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, get_current_principal


router = APIRouter(prefix="/batch", tags=["batch"])

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_TITLE_MODEL = "gemini-3.1-pro"


class BatchPreviewRequest(BaseModel):
    product_info: str = Field(min_length=1, max_length=4000)
    image_types: list[str] = Field(min_length=1, max_length=6)
    reference_count: int = Field(default=2, ge=1, le=10)
    include_titles: bool = Field(default=True)
    brief_notes: str = Field(default="", max_length=1200)


def build_type_label(image_type: str) -> str:
    mapping = {
        "main": "主图白底",
        "feature": "功能卖点",
        "scene": "场景应用",
        "detail": "细节特写",
        "size": "尺寸规格",
        "compare": "对比优势",
        "package": "清单展示",
        "steps": "使用步骤",
    }
    return mapping.get(image_type, image_type)


def build_batch_outputs(image_types: list[str], include_titles: bool) -> list[dict]:
    outputs = []
    for index, image_type in enumerate(image_types):
        outputs.append(
            {
                "id": f"batch-{index + 1}",
                "type": image_type,
                "label": build_type_label(image_type),
                "brief": f"{build_type_label(image_type)} · 适合批量电商素材输出",
                "title": (
                    f"Marketplace Ready {build_type_label(image_type)}"
                    if include_titles
                    else ""
                ),
            }
        )
    return outputs


@router.get("/meta")
def batch_meta(_principal: Principal = Depends(get_current_principal)):
    return {
        "image_types": [
            "main",
            "feature",
            "scene",
            "detail",
            "size",
            "compare",
            "package",
            "steps",
        ],
        "default_image_model": DEFAULT_IMAGE_MODEL,
        "default_title_model": DEFAULT_TITLE_MODEL,
        "max_reference_count": 10,
        "max_image_types": 6,
    }


@router.post("/preview")
def batch_preview(
    payload: BatchPreviewRequest,
    _principal: Principal = Depends(get_current_principal),
):
    outputs = build_batch_outputs(payload.image_types, payload.include_titles)
    return {
        "image_model": DEFAULT_IMAGE_MODEL,
        "title_model": DEFAULT_TITLE_MODEL,
        "reference_count": payload.reference_count,
        "total_outputs": len(outputs),
        "brief_summary": payload.brief_notes.strip() or "默认批量电商风格",
        "outputs": outputs,
    }
