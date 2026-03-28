from __future__ import annotations

from apps.api.routers.batch import DEFAULT_IMAGE_MODEL as BATCH_IMAGE_MODEL
from apps.api.routers.batch import DEFAULT_TITLE_MODEL as BATCH_TITLE_MODEL
from apps.api.routers.batch import build_batch_outputs
from apps.api.routers.quick import DEFAULT_IMAGE_MODEL as QUICK_IMAGE_MODEL
from apps.api.routers.quick import DEFAULT_TITLE_MODEL as QUICK_TITLE_MODEL
from apps.api.routers.quick import build_mock_outputs, build_prompt_summary
from apps.api.routers.title import DEFAULT_MODEL as TITLE_MODEL
from apps.api.routers.title import build_preview_titles
from apps.api.routers.translate import DEFAULT_ANALYSIS_MODEL
from apps.api.routers.translate import DEFAULT_IMAGE_MODEL
from apps.api.routers.translate import DEFAULT_PROVIDER
from apps.api.routers.translate import build_preview_translation
from temu_core.provider_capabilities import get_translation_provider_message
from temu_core.provider_precheck import describe_capability_reasons


def process_task_preview(task_type: str, payload: dict) -> dict:
    if task_type == "title_generation":
        titles = build_preview_titles(
            product_info=str(payload.get("productInfo") or ""),
            extra_requirements=str(payload.get("extraRequirements") or ""),
            tone=str(payload.get("tone") or "marketplace"),
            count=int(payload.get("count") or 3),
        )
        return {
            "titles": titles,
            "model": TITLE_MODEL,
            "source": "preview",
        }

    if task_type == "image_translate":
        provider = str(payload.get("provider") or DEFAULT_PROVIDER)
        image_model = str(payload.get("imageModel") or DEFAULT_IMAGE_MODEL)
        analysis_model = str(payload.get("analysisModel") or DEFAULT_ANALYSIS_MODEL)
        source_text = str(payload.get("sourceText") or "")
        target_lang = str(payload.get("targetLang") or "English")
        reasons = describe_capability_reasons(
            provider=provider,
            image_model=image_model,
            analysis_model=analysis_model,
            required_capabilities=["image_translate"],
        )
        return {
            "source_lines": [
                line.strip() for line in source_text.splitlines() if line.strip()
            ],
            "translated_lines": build_preview_translation(source_text, target_lang),
            "provider": provider,
            "image_model": image_model,
            "analysis_model": analysis_model,
            "provider_message": get_translation_provider_message(provider, image_model),
            "capability_reasons": reasons,
            "can_render_output_image": not reasons,
        }

    if task_type == "quick_generation":
        image_type = str(payload.get("imageType") or "main_visual")
        count = int(payload.get("count") or 4)
        include_titles = bool(payload.get("includeTitles", True))
        style_notes = str(payload.get("styleNotes") or "")
        titles = []
        if include_titles:
            titles = [
                f"Marketplace Ready {image_type.replace('_', ' ').title()} {index + 1}"
                for index in range(min(count, 3))
            ]
        return {
            "image_model": QUICK_IMAGE_MODEL,
            "title_model": QUICK_TITLE_MODEL,
            "prompt_summary": build_prompt_summary(image_type, style_notes),
            "outputs": build_mock_outputs(image_type, count),
            "titles": titles,
        }

    if task_type == "batch_generation":
        image_types = [
            str(item) for item in (payload.get("selectedTypes") or []) if str(item)
        ]
        include_titles = bool(payload.get("includeTitles", True))
        outputs = build_batch_outputs(image_types, include_titles)
        return {
            "image_model": BATCH_IMAGE_MODEL,
            "title_model": BATCH_TITLE_MODEL,
            "reference_count": int(payload.get("referenceCount") or 2),
            "total_outputs": len(outputs),
            "brief_summary": str(payload.get("briefNotes") or "").strip()
            or "默认批量电商风格",
            "outputs": outputs,
        }

    raise ValueError(f"Unsupported task type: {task_type}")
