from __future__ import annotations

from typing import Any

from apps.api.core.personal_config import get_effective_execution_config_for_user
from apps.api.core.system_config import get_system_execution_config
from temu_core.ai_clients import build_image_client
from temu_core.ai_clients import build_text_client
from temu_core.ai_clients import image_from_data_url
from temu_core.ai_clients import image_to_data_url
from temu_core.provider_capabilities import get_translation_provider_message
from temu_core.provider_capabilities import model_supports
from temu_core.provider_precheck import describe_capability_reasons
from temu_core.relay_first_logic import analyze_product_with_text_client
from temu_core.title_logic import generate_compliant_titles_or_raise


MIN_TITLE_EN_CHARS = 180
MAX_TITLE_EN_CHARS = 250

STRICT_COMPLIANCE_BLACKLIST = [
    "FDA",
    "CE",
    "ISO",
    "certified",
    "approved",
    "medical",
    "cure",
    "treat",
    "heal",
    "best",
    "perfect",
    "100%",
    "guarantee",
    "forever",
    "only",
    "No.1",
    "first",
    "authentic",
    "genuine",
    "official",
    "organic",
    "natural",
    "pure",
    "real",
]

TITLE_TEMPLATE_CATALOG = {
    "default": {
        "name": "TEMU标准优化（中英双语）",
        "desc": "完整规则，中英双语输出，强调平台搜索与转化。",
        "prompt": """ROLE You are an ecommerce title optimization expert for TEMU and similar marketplace search systems.
INPUT I will provide product text description, product images, or both.
TASK Generate exactly {count} product title candidates for the same product. Each candidate must have BOTH English and Chinese versions.
STYLE Tone preference: {tone}
RULES
- Each title candidate must use two lines: English first, Chinese second.
- English titles must be between {min_chars} and {max_chars} characters.
- Output plain text only with no numbering or explanations.
- Use only truthful details from the provided product information and visible image details.
- Avoid compliance-risk claims and exaggerated wording.
- Create distinct focuses for search, conversion, and differentiation.

PRODUCT INFORMATION
{product_info}

ADDITIONAL REQUIREMENTS
{extra_requirements}

OUTPUT FORMAT
Return exactly {line_count} lines: English then Chinese for each title candidate.
""",
    },
    "simple": {
        "name": "简洁高效（中英双语）",
        "desc": "快速生成，中英双语输出。",
        "prompt": """Generate exactly {count} bilingual product title candidates for TEMU marketplace.
Tone preference: {tone}
Product information:
{product_info}
Additional requirements:
{extra_requirements}

Rules:
- English line first, Chinese line second for each candidate.
- English title length {min_chars}-{max_chars} characters.
- Plain text only.
- No invented features, no exaggerated claims.
- Output exactly {line_count} lines.
""",
    },
    "detailed": {
        "name": "详细规格（中英双语）",
        "desc": "适合规格复杂的商品，突出参数与场景。",
        "prompt": """You are a TEMU title expert creating exactly {count} bilingual title candidates.
Tone preference: {tone}
Use the product details below to create search-first, conversion-first, and differentiation-first variants.

Product details:
{product_info}

Additional requirements:
{extra_requirements}

Rules:
- English line first and Chinese translation second for each candidate.
- English title length must stay between {min_chars} and {max_chars} characters.
- Include specifications only when they are provided or visible.
- Do not invent features or unsupported claims.
- Output exactly {line_count} lines.
""",
    },
    "image_analysis": {
        "name": "图片智能分析（中英双语）",
        "desc": "根据商品图片分析后生成中英双语标题。",
        "prompt": """Analyze the product image references and generate exactly {count} bilingual title candidates for TEMU marketplace.
Tone preference: {tone}
Additional info:
{product_info}

Based on the images, identify product category, visible features, materials, colors, design, and likely use cases.

Rules:
- English line first and Chinese line second for each candidate.
- English title length must stay between {min_chars} and {max_chars} characters.
- Do not invent features not visible in the images or supported by the additional info.
- Avoid compliance-risk or exaggerated claims.
- Output exactly {line_count} lines.
""",
    },
}

DEFAULT_TITLE_TEMPLATE_KEY = "default"
IMAGE_TITLE_TEMPLATE_KEY = "image_analysis"

TRANSLATE_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "heif"}
TRANSLATE_ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/heic",
    "image/heif",
}
TRANSLATE_MAX_UPLOADS = 6
TRANSLATE_MAX_FILE_MB = 7
IMAGE_REF_MAX_UPLOADS = 6
IMAGE_REF_EFFECTIVE_COUNT = 5
IMAGE_REF_MAX_FILE_MB = 7
IMAGE_REF_ALLOWED_EXTENSIONS = TRANSLATE_ALLOWED_EXTENSIONS
IMAGE_REF_ALLOWED_MIME_TYPES = TRANSLATE_ALLOWED_MIME_TYPES


def execute_title_task(payload: dict[str, Any]) -> dict[str, Any]:
    config = _get_execution_config(payload)
    product_info = str(payload.get("productInfo") or "").strip()
    extra_requirements = str(payload.get("extraRequirements") or "").strip()
    tone = str(payload.get("tone") or "marketplace").strip() or "marketplace"
    template_key = _resolve_title_template_key(
        payload, has_refs=bool(payload.get("uploadItems"))
    )
    count = max(1, min(int(payload.get("count") or 3), 5))
    upload_items = [
        item for item in (payload.get("uploadItems") or []) if isinstance(item, dict)
    ]
    refs: list[Any] = []
    normalized_uploads: list[dict[str, Any]] = []

    if upload_items:
        refs, normalized_uploads = _prepare_image_refs(upload_items)

    if not product_info and not refs:
        raise ValueError("请先输入商品信息，再生成标题。")

    provider = _resolve_title_provider(config)
    template = TITLE_TEMPLATE_CATALOG[template_key]
    client = build_text_client(
        provider=provider,
        model=config.title_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )
    titles, warnings = generate_compliant_titles_or_raise(
        client=client,
        images=refs,
        product_info=_build_title_product_info(
            product_info or ("No additional info provided" if refs else ""),
            extra_requirements,
        ),
        template_prompt=template["prompt"].format(
            count=count,
            tone=tone,
            min_chars=MIN_TITLE_EN_CHARS,
            max_chars=MAX_TITLE_EN_CHARS,
            line_count=count * 2,
            extra_requirements=extra_requirements or "None",
            product_info="{product_info}",
        ),
        compliance_checker=_check_title_compliance,
        compliance_mode="strict",
    )
    normalized_titles = _limit_title_lines(titles, count)

    return {
        "titles": normalized_titles,
        "title_pairs": _build_title_pairs(normalized_titles),
        "model": config.title_model,
        "provider": provider,
        "warnings": warnings,
        "execution_mode": "image_refs" if refs else "text",
        "upload_count": len(normalized_uploads),
        "reference_count": len(refs),
        "template_key": template_key,
        "template_name": str(template.get("name") or ""),
        "compliance_mode": "strict",
        "execution_context": {
            "config_source": str(getattr(config, "source", "") or "environment"),
            "project_id": str(payload.get("projectId") or ""),
            "project_name": str(payload.get("projectName") or ""),
            "project_slug": str(payload.get("projectSlug") or ""),
            "submitted_via": "jobs",
            "task_type": "title_generation",
        },
        "source": "execution",
        "tokens_used": getattr(client, "get_tokens_used", lambda: 0)(),
    }


def execute_translate_task(payload: dict[str, Any]) -> dict[str, Any]:
    config = _get_execution_config(payload)
    source_text = str(payload.get("sourceText") or "").strip()
    source_lang = str(payload.get("sourceLang") or "auto").strip() or "auto"
    target_lang = str(payload.get("targetLang") or "English").strip() or "English"
    upload_items = [
        item for item in (payload.get("uploadItems") or []) if isinstance(item, dict)
    ]

    if upload_items:
        return _execute_translate_image_batch(
            payload=payload,
            upload_items=upload_items,
            source_lang=source_lang,
            target_lang=target_lang,
            config=config,
        )

    if not source_text:
        raise ValueError("请先输入要翻译的图片文案或 OCR 文本。")

    provider = config.translate_provider
    image_model = config.translate_image_model
    analysis_model = config.translate_analysis_model
    client = build_text_client(
        provider=provider,
        model=analysis_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )

    source_lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    translated_lines = client.translate_lines(
        source_lines,
        source_lang=source_lang,
        target_lang=target_lang,
        style_hint="Marketplace-ready",
        enforce_english=target_lang.lower() == "english",
        max_attempts=2,
    )
    if not translated_lines:
        last_error = getattr(client, "get_last_error", lambda: "")()
        raise ValueError(last_error or "翻译执行失败，模型未返回可用结果。")

    capability_reasons = describe_capability_reasons(
        provider=provider,
        image_model=image_model,
        analysis_model=analysis_model,
        required_capabilities=["image_translate"],
    )
    return {
        "source_lines": source_lines,
        "translated_lines": translated_lines,
        "provider": provider,
        "image_model": image_model,
        "analysis_model": analysis_model,
        "provider_message": get_translation_provider_message(provider, image_model),
        "capability_reasons": capability_reasons,
        "can_render_output_image": not capability_reasons,
        "execution_mode": "text",
        "source": "execution",
        "tokens_used": getattr(client, "get_tokens_used", lambda: 0)(),
    }


def _execute_translate_image_batch(
    *,
    payload: dict[str, Any],
    upload_items: list[dict[str, Any]],
    source_lang: str,
    target_lang: str,
    config,
) -> dict[str, Any]:
    del payload
    if len(upload_items) > TRANSLATE_MAX_UPLOADS:
        raise ValueError(f"图片翻译首版一次最多支持 {TRANSLATE_MAX_UPLOADS} 张图片。")
    if target_lang.lower() != "english":
        raise ValueError("图片翻译首版仅支持输出英文译图，请将目标语言切换为 English。")

    provider = config.translate_provider
    image_model = config.translate_image_model
    analysis_model = config.translate_analysis_model
    capability_reasons = describe_capability_reasons(
        provider=provider,
        image_model=image_model,
        analysis_model=analysis_model,
        required_capabilities=["image_translate"],
    )
    can_render_output_image = not capability_reasons
    text_client = build_text_client(
        provider=provider,
        model=analysis_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )
    image_client = build_image_client(
        provider=_resolve_image_provider(image_model, config),
        model=image_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )

    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    first_source_lines: list[str] = []
    first_translated_lines: list[str] = []
    completed_outputs = 0

    for index, item in enumerate(upload_items):
        normalized = _normalize_translate_upload_item(item)
        image = image_from_data_url(normalized["image_data_url"])
        extracted = text_client.extract_and_translate_image_text(
            image,
            source_lang=source_lang,
            target_lang="English",
            style_hint="Marketplace-ready",
            enforce_english=True,
            max_attempts=2,
        )
        source_lines = [
            str(line).strip()
            for line in (extracted.get("source_lines") or [])
            if str(line).strip()
        ]
        translated_lines = [
            str(line).strip()
            for line in (extracted.get("translated_lines") or [])
            if str(line).strip()
        ]
        if not source_lines and not translated_lines:
            source_lines = text_client.extract_text_from_image(
                image, source_lang=source_lang
            ).get("lines", [])
            translated_lines = text_client.translate_lines(
                source_lines,
                source_lang=source_lang,
                target_lang="English",
                style_hint="Marketplace-ready",
                enforce_english=True,
                max_attempts=2,
            )

        item_result = {
            "id": normalized["id"],
            "label": f"翻译结果 {index + 1}",
            "raw_name": normalized["raw_name"],
            "filename": _build_translate_filename(normalized["raw_name"], index),
            "source_lines": source_lines,
            "translated_lines": translated_lines,
        }

        if source_lines and translated_lines and not first_source_lines:
            first_source_lines = source_lines
            first_translated_lines = translated_lines

        if not translated_lines:
            error = getattr(text_client, "get_last_error", lambda: "")() or (
                f"{normalized['raw_name']} OCR/翻译失败"
            )
            outputs.append({**item_result, "status": "failed", "error": error})
            errors.append(error)
            continue

        if not can_render_output_image:
            error = (
                capability_reasons[0]
                if capability_reasons
                else "当前配置暂不支持译后出图。"
            )
            outputs.append({**item_result, "status": "failed", "error": error})
            errors.append(error)
            continue

        translated_image = image_client.translate_image(
            image,
            translated_lines,
            source_lines=source_lines,
            preserve_ratio=True,
            size="1K",
            remove_overlay_text=True,
        )
        if translated_image is None:
            error = getattr(image_client, "get_last_error", lambda: "")() or (
                f"{normalized['raw_name']} 译后图片生成失败"
            )
            outputs.append({**item_result, "status": "failed", "error": error})
            errors.append(error)
            continue

        completed_outputs += 1
        outputs.append(
            {
                **item_result,
                "status": "completed",
                "artifact_data_url": image_to_data_url(translated_image),
            }
        )

    total_outputs = len(outputs)
    failed_outputs = total_outputs - completed_outputs
    tokens_used = int(getattr(text_client, "get_tokens_used", lambda: 0)() or 0) + int(
        getattr(image_client, "get_tokens_used", lambda: 0)() or 0
    )
    return {
        "source_lines": first_source_lines,
        "translated_lines": first_translated_lines,
        "provider": provider,
        "image_model": image_model,
        "analysis_model": analysis_model,
        "provider_message": get_translation_provider_message(provider, image_model),
        "capability_reasons": capability_reasons,
        "can_render_output_image": can_render_output_image,
        "execution_mode": "image_batch",
        "outputs": outputs,
        "errors": errors,
        "total_outputs": total_outputs,
        "completed_outputs": completed_outputs,
        "failed_outputs": failed_outputs,
        "source": "execution",
        "tokens_used": tokens_used,
    }


def _normalize_translate_upload_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_name = (
        str(item.get("rawName") or "translate-image.png").strip()
        or "translate-image.png"
    )
    mime_type = str(item.get("mimeType") or "").strip().lower()
    size_bytes = int(item.get("sizeBytes") or 0)
    image_data_url = str(item.get("imageDataUrl") or "").strip()
    item_id = str(item.get("id") or raw_name).strip() or raw_name
    extension = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""

    if not image_data_url:
        raise ValueError(f"{raw_name} 缺少图片内容，无法执行图片翻译。")
    if extension and extension not in TRANSLATE_ALLOWED_EXTENSIONS:
        raise ValueError(f"{raw_name} 格式不支持，请上传 PNG/JPG/JPEG/WEBP/HEIC/HEIF。")
    if mime_type and mime_type not in TRANSLATE_ALLOWED_MIME_TYPES:
        raise ValueError(f"{raw_name} MIME 类型不支持，请重新上传标准图片文件。")
    if size_bytes <= 0:
        raise ValueError(f"{raw_name} 文件大小异常，请重新选择图片。")
    if size_bytes > TRANSLATE_MAX_FILE_MB * 1024 * 1024:
        raise ValueError(
            f"{raw_name} 超过 {TRANSLATE_MAX_FILE_MB}MB 限制，请压缩后重试。"
        )

    return {
        "id": item_id,
        "raw_name": raw_name,
        "mime_type": mime_type or f"image/{extension or 'png'}",
        "size_bytes": size_bytes,
        "image_data_url": image_data_url,
    }


def _build_translate_filename(raw_name: str, index: int) -> str:
    base_name = raw_name.rsplit(".", 1)[0].strip() or f"translate-{index + 1}"
    return f"{base_name}-translated.png"


def execute_quick_task(payload: dict[str, Any]) -> dict[str, Any]:
    config = _get_execution_config(payload)
    product_info = str(payload.get("productInfo") or "").strip()
    image_type = (
        str(payload.get("imageType") or "selling_point").strip() or "selling_point"
    )
    count = max(1, min(int(payload.get("count") or 4), 6))
    include_titles = bool(payload.get("includeTitles", True))
    style_notes = str(payload.get("styleNotes") or "").strip()
    upload_items = [
        item for item in (payload.get("uploadItems") or []) if isinstance(item, dict)
    ]

    if not upload_items and not product_info:
        raise ValueError("请先上传 1-6 张商品图片，再生成快速出图。")
    refs: list[Any] = []
    normalized_uploads: list[dict[str, Any]] = []
    if upload_items:
        refs, normalized_uploads = _prepare_image_refs(upload_items)

    provider = _resolve_image_provider(config.quick_image_model, config)
    client = build_image_client(
        provider=provider,
        model=config.quick_image_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )

    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    for index in range(count):
        label = f"{_quick_label(image_type)} {index + 1}"
        prompt = _build_quick_prompt(product_info, image_type, style_notes, index)
        image = client.generate_image(refs, prompt, aspect="1:1", size="1K")
        if image is None:
            last_error = (
                getattr(client, "get_last_error", lambda: "")() or f"{label} 生成失败"
            )
            errors.append(last_error)
            outputs.append(
                {
                    "id": f"quick-{index + 1}",
                    "label": label,
                    "status": "failed",
                    "error": last_error,
                }
            )
            continue

        outputs.append(
            {
                "id": f"quick-{index + 1}",
                "label": label,
                "status": "completed",
                "artifact_data_url": image_to_data_url(image),
                "prompt": prompt,
                "filename": f"{image_type.replace('_', '-')}-{index + 1}.png",
            }
        )

    titles: list[str] = []
    title_warnings: list[str] = []
    title_tokens = 0
    if include_titles:
        titles, title_warnings, title_tokens, title_error = _generate_optional_titles(
            product_info=product_info,
            extra_requirements=style_notes,
            count=min(count, 3),
            owner_id=str(payload.get("ownerId") or "").strip(),
        )
        if title_error:
            errors.append(title_error)

    return {
        "image_model": config.quick_image_model,
        "title_model": config.title_model,
        "provider": provider,
        "execution_mode": "image_refs" if normalized_uploads else "text",
        "upload_count": len(normalized_uploads),
        "reference_count": len(refs),
        "image_type": image_type,
        "prompt_summary": _build_quick_summary(image_type, style_notes),
        "outputs": outputs,
        "titles": titles,
        "title_warnings": title_warnings,
        "tokens_used": getattr(client, "get_tokens_used", lambda: 0)() + title_tokens,
        "errors": errors,
        "source": "execution",
    }


def _build_title_product_info(product_info: str, extra_requirements: str) -> str:
    if not extra_requirements:
        return product_info
    return f"{product_info}\n\nExtra requirements:\n{extra_requirements}"


def list_title_template_options() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "name": str(item.get("name") or key),
            "desc": str(item.get("desc") or ""),
        }
        for key, item in TITLE_TEMPLATE_CATALOG.items()
    ]


def _resolve_title_template_key(payload: dict[str, Any], *, has_refs: bool) -> str:
    requested = str(payload.get("templateKey") or "").strip()
    if requested in TITLE_TEMPLATE_CATALOG:
        return requested
    if has_refs:
        return IMAGE_TITLE_TEMPLATE_KEY
    return DEFAULT_TITLE_TEMPLATE_KEY


def _limit_title_lines(titles: list[str], count: int) -> list[str]:
    if len(titles) >= count * 2 and len(titles) % 2 == 0:
        return titles[: count * 2]
    return titles[:count]


def _build_title_pairs(titles: list[str]) -> list[dict[str, Any]]:
    labels = ["搜索优化", "转化优化", "差异化"]
    pairs: list[dict[str, Any]] = []
    for index in range(0, len(titles), 2):
        english = str(titles[index] or "").strip()
        chinese = (
            str(titles[index + 1] or "").strip() if index + 1 < len(titles) else ""
        )
        en_chars = len(english)
        pair_index = index // 2
        pairs.append(
            {
                "index": pair_index + 1,
                "label": labels[pair_index]
                if pair_index < len(labels)
                else f"标题 {pair_index + 1}",
                "english": english,
                "chinese": chinese,
                "english_char_count": en_chars,
                "english_char_in_range": MIN_TITLE_EN_CHARS
                <= en_chars
                <= MAX_TITLE_EN_CHARS,
            }
        )
    return pairs


def _check_title_compliance(text: str, mode: str = "strict"):
    del mode
    if not text:
        return True, text, ""
    text_lower = text.lower()
    hits = [term for term in STRICT_COMPLIANCE_BLACKLIST if term.lower() in text_lower]
    if hits:
        return False, text, f"风险词: {', '.join(hits[:5])}"
    return True, text, ""


def _get_execution_config(payload: dict[str, Any]):
    owner_id = str(payload.get("ownerId") or "").strip()
    if owner_id:
        return get_effective_execution_config_for_user(owner_id)
    return get_system_execution_config()


def _resolve_title_provider(config) -> str:
    title_model = str(config.title_model or "").strip()
    gemini_available = bool(str(config.gemini_api_key or "").strip())
    relay_available = bool(
        str(config.relay_api_key or "").strip()
        and str(config.relay_api_base or "").strip()
    )

    if title_model.lower().startswith("gemini"):
        if gemini_available:
            return "gemini"
        if relay_available and model_supports("relay", title_model, "text_generation"):
            return "relay"
        raise ValueError(
            f"当前标题模型 `{title_model}` 需要可用的 Gemini Key，或切换到支持 relay 文本生成的模型。"
        )

    if relay_available and model_supports("relay", title_model, "text_generation"):
        return "relay"
    if gemini_available:
        raise ValueError(
            f"当前标题模型 `{title_model}` 不是 Gemini 原生标题模型，请改用支持 relay 文本生成的模型，或切换到 Gemini 标题模型。"
        )
    raise ValueError(
        "当前未配置可用的标题执行凭据，请先在管理后台配置 Gemini 或中转站。"
    )


def _resolve_image_provider(image_model: str, config) -> str:
    if (
        str(config.relay_api_key or "").strip()
        and str(config.relay_api_base or "").strip()
        and model_supports("relay", image_model, "image_generate")
    ):
        return "relay"
    if str(config.gemini_api_key or "").strip():
        return "gemini"
    if (
        str(config.relay_api_key or "").strip()
        and str(config.relay_api_base or "").strip()
    ):
        return "relay"
    raise ValueError(
        "当前未配置可用的图片生成凭据，请先在管理后台配置 Gemini 或中转站。"
    )


def _quick_label(image_type: str) -> str:
    return {
        "selling_point": "卖点图",
        "scene": "场景图",
        "detail": "细节图",
        "comparison": "对比图",
        "spec": "规格图",
    }.get(image_type, "快速出图版本")


def _build_quick_summary(image_type: str, style_notes: str) -> str:
    base = _quick_label(image_type)
    if style_notes:
        return f"{base} · {style_notes}"
    return f"{base} · 默认电商风格"


def _build_quick_prompt(
    product_info: str, image_type: str, style_notes: str, index: int
) -> str:
    type_hint = {
        "selling_point": "selling-point product image",
        "scene": "lifestyle scene image",
        "detail": "detail close-up image",
        "comparison": "comparison advantage image",
        "spec": "specification infographic image",
    }.get(image_type, "ecommerce product image")
    variant = index + 1
    return (
        f"Create one {type_hint} for an ecommerce product. "
        f"Product info: {product_info}. "
        f"Style notes: {style_notes or 'clean white-background marketplace style'}. "
        f"Variant: {variant}. English text only if any text is rendered."
    )


def execute_batch_task(payload: dict[str, Any]) -> dict[str, Any]:
    config = _get_execution_config(payload)
    product_info = str(payload.get("productInfo") or "").strip()
    selected_types = [
        str(item).strip()
        for item in (payload.get("selectedTypes") or [])
        if str(item).strip()
    ]
    reference_count = max(1, min(int(payload.get("referenceCount") or 2), 6))
    include_titles = bool(payload.get("includeTitles", True))
    brief_notes = str(payload.get("briefNotes") or "").strip()
    upload_items = [
        item for item in (payload.get("uploadItems") or []) if isinstance(item, dict)
    ]

    if not upload_items and not product_info:
        raise ValueError("请先上传 1-6 张商品图片，再生成批量出图。")
    if not selected_types:
        raise ValueError("请至少选择一种出图类型。")
    refs: list[Any] = []
    normalized_uploads: list[dict[str, Any]] = []
    if upload_items:
        refs, normalized_uploads = _prepare_image_refs(upload_items)

    provider = _resolve_image_provider(config.batch_image_model, config)
    client = build_image_client(
        provider=provider,
        model=config.batch_image_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )

    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    generated_titles: list[str] = []
    title_warnings: list[str] = []
    title_tokens = 0
    text_client = build_text_client(
        provider=config.translate_provider,
        model=config.translate_analysis_model,
        gemini_api_key=config.gemini_api_key,
        relay_api_key=config.relay_api_key,
        relay_api_base=config.relay_api_base,
    )
    anchor = analyze_product_with_text_client(
        images=refs,
        product_name=product_info,
        text_client=text_client,
    )

    for index, image_type in enumerate(selected_types):
        label = _batch_label(image_type)
        prompt = _build_batch_prompt(
            product_info, image_type, brief_notes, index, anchor
        )
        image = client.generate_image(refs, prompt, aspect="1:1", size="1K")
        title = generated_titles[index] if index < len(generated_titles) else ""
        if image is None:
            last_error = (
                getattr(client, "get_last_error", lambda: "")() or f"{label} 生成失败"
            )
            errors.append(last_error)
            outputs.append(
                {
                    "id": f"batch-{index + 1}",
                    "type": image_type,
                    "label": label,
                    "status": "failed",
                    "error": last_error,
                    "title": title,
                    "filename": f"{image_type.replace('_', '-')}-{index + 1}.png",
                }
            )
            continue

        outputs.append(
            {
                "id": f"batch-{index + 1}",
                "type": image_type,
                "label": label,
                "status": "completed",
                "artifact_data_url": image_to_data_url(image),
                "prompt": prompt,
                "title": title,
                "filename": f"{image_type.replace('_', '-')}-{index + 1}.png",
            }
        )

    if include_titles:
        (
            generated_titles,
            title_warnings,
            title_tokens,
            title_error,
        ) = _generate_optional_titles(
            product_info=product_info,
            extra_requirements=brief_notes,
            count=min(len(selected_types), 5),
            owner_id=str(payload.get("ownerId") or "").strip(),
        )
        if title_error:
            errors.append(title_error)

        for index, output in enumerate(outputs):
            output["title"] = (
                generated_titles[index] if index < len(generated_titles) else ""
            )

    return {
        "image_model": config.batch_image_model,
        "analysis_model": config.translate_analysis_model,
        "title_model": config.title_model,
        "provider": provider,
        "execution_mode": "image_refs" if normalized_uploads else "text",
        "upload_count": len(normalized_uploads),
        "reference_count": len(refs),
        "anchor": anchor,
        "total_outputs": len(outputs),
        "brief_summary": brief_notes or "默认批量电商风格",
        "outputs": outputs,
        "titles": generated_titles,
        "title_warnings": title_warnings,
        "errors": errors,
        "source": "execution",
        "tokens_used": getattr(client, "get_tokens_used", lambda: 0)() + title_tokens,
    }


def _generate_optional_titles(
    *,
    product_info: str,
    extra_requirements: str,
    count: int,
    owner_id: str = "",
) -> tuple[list[str], list[str], int, str]:
    try:
        title_result = execute_title_task(
            {
                "productInfo": product_info,
                "extraRequirements": extra_requirements,
                "tone": "marketplace",
                "count": count,
                **({"ownerId": owner_id} if owner_id else {}),
            }
        )
    except Exception as exc:
        message = f"标题生成失败，已保留图片结果：{exc}"
        return [], [message], 0, message

    titles = [str(item) for item in title_result.get("titles", []) if str(item).strip()]
    warnings = [
        str(item) for item in title_result.get("warnings", []) if str(item).strip()
    ]
    tokens_used = int(title_result.get("tokens_used") or 0)
    return titles, warnings, tokens_used, ""


def _batch_label(image_type: str) -> str:
    return {
        "main": "主图白底",
        "feature": "功能卖点",
        "scene": "场景应用",
        "detail": "细节特写",
        "size": "尺寸规格",
        "compare": "对比优势",
        "package": "清单展示",
        "steps": "使用步骤",
    }.get(image_type, image_type)


def _build_batch_prompt(
    product_info: str,
    image_type: str,
    brief_notes: str,
    index: int,
    anchor: dict[str, Any],
) -> str:
    visual_attrs = ", ".join(
        [
            str(item).strip()
            for item in (anchor.get("visual_attrs") or [])
            if str(item).strip()
        ]
    )
    return (
        f"Create one ecommerce batch asset for type {image_type}. "
        f"Product info: {product_info or anchor.get('product_name_en') or anchor.get('product_name_zh')}. "
        f"Primary category: {anchor.get('primary_category') or 'unknown'}. "
        f"Visual attributes: {visual_attrs or 'clean marketplace product refs'}. "
        f"Batch brief: {brief_notes or 'clean marketplace campaign style'}. "
        f"Variant: {index + 1}. English text only if any text is rendered."
    )


def _prepare_image_refs(
    upload_items: list[dict[str, Any]],
) -> tuple[list[Any], list[dict[str, Any]]]:
    if len(upload_items) > IMAGE_REF_MAX_UPLOADS:
        raise ValueError(f"一次最多上传 {IMAGE_REF_MAX_UPLOADS} 张商品图片。")
    normalized_uploads = [
        _normalize_image_ref_upload_item(item)
        for item in upload_items[:IMAGE_REF_MAX_UPLOADS]
    ]
    refs = [
        image_from_data_url(item["image_data_url"])
        for item in normalized_uploads[:IMAGE_REF_EFFECTIVE_COUNT]
    ]
    return refs, normalized_uploads


def _normalize_image_ref_upload_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_name = (
        str(item.get("rawName") or "reference-image.png").strip()
        or "reference-image.png"
    )
    mime_type = str(item.get("mimeType") or "").strip().lower()
    size_bytes = int(item.get("sizeBytes") or 0)
    image_data_url = str(item.get("imageDataUrl") or "").strip()
    item_id = str(item.get("id") or raw_name).strip() or raw_name
    extension = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""

    if not image_data_url:
        raise ValueError(f"{raw_name} 缺少图片内容，无法执行出图。")
    if extension and extension not in IMAGE_REF_ALLOWED_EXTENSIONS:
        raise ValueError(f"{raw_name} 格式不支持，请上传 PNG/JPG/JPEG/WEBP/HEIC/HEIF。")
    if mime_type and mime_type not in IMAGE_REF_ALLOWED_MIME_TYPES:
        raise ValueError(f"{raw_name} MIME 类型不支持，请重新上传标准图片文件。")
    if size_bytes <= 0:
        raise ValueError(f"{raw_name} 文件大小异常，请重新选择图片。")
    if size_bytes > IMAGE_REF_MAX_FILE_MB * 1024 * 1024:
        raise ValueError(
            f"{raw_name} 超过 {IMAGE_REF_MAX_FILE_MB}MB 限制，请压缩后重试。"
        )

    return {
        "id": item_id,
        "raw_name": raw_name,
        "mime_type": mime_type or f"image/{extension or 'png'}",
        "size_bytes": size_bytes,
        "image_data_url": image_data_url,
    }
