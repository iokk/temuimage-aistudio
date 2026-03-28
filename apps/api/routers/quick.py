from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/quick", tags=["quick"])

DEFAULT_IMAGE_MODEL = "seedream-5.0"
DEFAULT_TITLE_MODEL = "gemini-3.1-flash-lite-preview"


class QuickPreviewRequest(BaseModel):
    product_info: str = Field(min_length=1, max_length=4000)
    image_type: str = Field(default="main_visual", max_length=100)
    count: int = Field(default=4, ge=1, le=6)
    include_titles: bool = Field(default=True)
    style_notes: str = Field(default="", max_length=1000)


def build_prompt_summary(image_type: str, style_notes: str) -> str:
    type_labels = {
        "main_visual": "主图强化",
        "detail_card": "卖点细节图",
        "scene_banner": "场景横幅图",
    }
    type_label = type_labels.get(image_type, "快速出图")
    if style_notes.strip():
        return f"{type_label} · {style_notes.strip()}"
    return f"{type_label} · 默认电商风格"


def build_mock_outputs(image_type: str, count: int) -> list[dict]:
    labels = {
        "main_visual": "主图版本",
        "detail_card": "细节卡版本",
        "scene_banner": "场景图版本",
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
def quick_meta():
    return {
        "image_types": ["main_visual", "detail_card", "scene_banner"],
        "default_image_model": DEFAULT_IMAGE_MODEL,
        "default_title_model": DEFAULT_TITLE_MODEL,
        "max_count": 6,
    }


@router.post("/preview")
def quick_preview(payload: QuickPreviewRequest):
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
