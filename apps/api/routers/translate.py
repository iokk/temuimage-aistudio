from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, get_current_principal
from temu_core.provider_capabilities import get_translation_provider_message
from temu_core.provider_precheck import describe_capability_reasons


router = APIRouter(prefix="/translate", tags=["translate"])

DEFAULT_PROVIDER = "relay"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_ANALYSIS_MODEL = "gemini-3.1-pro"


class TranslatePreviewRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=4000)
    source_lang: str = Field(default="auto", max_length=50)
    target_lang: str = Field(default="English", max_length=50)
    provider: str = Field(default=DEFAULT_PROVIDER, max_length=50)
    image_model: str = Field(default=DEFAULT_IMAGE_MODEL, max_length=100)
    analysis_model: str = Field(default=DEFAULT_ANALYSIS_MODEL, max_length=100)


def build_preview_translation(source_text: str, target_lang: str) -> list[str]:
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    if not lines:
        return []

    translated = []
    for line in lines:
        translated.append(f"[{target_lang}] {line}")
    return translated


@router.get("/meta")
def translate_meta(_principal: Principal = Depends(get_current_principal)):
    return {
        "provider_options": ["relay", "gemini"],
        "image_model_options": [
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
            "seedream-5.0",
            "seedream-4.6",
        ],
        "analysis_model_options": [
            "gemini-3.1-pro",
            "gemini-3.1-flash-image-preview",
        ],
        "default_provider": DEFAULT_PROVIDER,
        "default_image_model": DEFAULT_IMAGE_MODEL,
        "default_analysis_model": DEFAULT_ANALYSIS_MODEL,
    }


@router.post("/preview")
def translate_preview(
    payload: TranslatePreviewRequest,
    _principal: Principal = Depends(get_current_principal),
):
    reasons = describe_capability_reasons(
        provider=payload.provider,
        image_model=payload.image_model,
        analysis_model=payload.analysis_model,
        required_capabilities=["image_translate"],
    )
    translated_lines = build_preview_translation(
        source_text=payload.source_text,
        target_lang=payload.target_lang,
    )
    provider_message = get_translation_provider_message(
        payload.provider,
        payload.image_model,
    )

    return {
        "source_lines": [
            line.strip() for line in payload.source_text.splitlines() if line.strip()
        ],
        "translated_lines": translated_lines,
        "provider": payload.provider,
        "image_model": payload.image_model,
        "analysis_model": payload.analysis_model,
        "provider_message": provider_message,
        "capability_reasons": reasons,
        "can_render_output_image": not reasons,
    }
