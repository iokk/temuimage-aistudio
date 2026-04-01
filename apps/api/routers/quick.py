from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, get_current_principal


router = APIRouter(prefix="/quick", tags=["quick"])

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_TITLE_MODEL = "gemini-3.1-pro"


class QuickPreviewRequest(BaseModel):
    product_info: str = Field(min_length=1, max_length=4000)
    image_type: str = Field(default="selling_point", max_length=100)
    count: int = Field(default=4, ge=1, le=6)
    include_titles: bool = Field(default=True)
    style_notes: str = Field(default="", max_length=1000)


def build_prompt_summary(image_type: str, style_notes: str) -> str:
    type_labels = {
        "selling_point": "卖点图",
        "scene": "场景图",
        "detail": "细节图",
        "comparison": "对比图",
        "spec": "规格图",
    }
    type_label = type_labels.get(image_type, "快速出图")
    if style_notes.strip():
        return f"{type_label} · {style_notes.strip()}"
    return f"{type_label} · 默认电商风格"


def build_mock_outputs(image_type: str, count: int) -> list[dict]:
    labels = {
        "selling_point": "卖点图",
        "scene": "场景图",
        "detail": "细节图",
        "comparison": "对比图",
        "spec": "规格图",
    }
    prefix = labels.get(image_type, "出图版本")
    outputs = []
    for index in range(count):
        outputs.append(
            {
                "id": f"quick-{index + 1}",
                "label": f"{prefix} {index + 1}",
                "preview_text": f"{prefix} {index + 1} · 适合跨境电商投放与详情展示",
            }
        )
    return outputs


@router.get("/meta")
def quick_meta(_principal: Principal = Depends(get_current_principal)):
    return {
        "image_types": [
            "selling_point",
            "scene",
            "detail",
            "comparison",
            "spec",
        ],
        "default_image_model": DEFAULT_IMAGE_MODEL,
        "default_title_model": DEFAULT_TITLE_MODEL,
        "max_count": 6,
    }


@router.post("/preview")
def quick_preview(
    payload: QuickPreviewRequest,
    _principal: Principal = Depends(get_current_principal),
):
    prompt_summary = build_prompt_summary(payload.image_type, payload.style_notes)
    titles = []
    if payload.include_titles:
        titles = [
            f"Marketplace Ready {payload.image_type.replace('_', ' ').title()} {index + 1}"
            for index in range(min(payload.count, 3))
        ]

    return {
        "image_model": DEFAULT_IMAGE_MODEL,
        "title_model": DEFAULT_TITLE_MODEL,
        "prompt_summary": prompt_summary,
        "outputs": build_mock_outputs(payload.image_type, payload.count),
        "titles": titles,
    }
