from __future__ import annotations


DEFAULT_CAPABILITIES = {
    "image_generate": False,
    "image_translate": False,
    "image_analysis": False,
    "title_from_image": False,
    "text_generation": False,
}


CAPABILITY_MATRIX = {
    ("relay", "gemini-3.1-flash-image-preview"): {
        "image_generate": True,
        "image_translate": True,
        "image_analysis": True,
        "title_from_image": True,
        "text_generation": True,
    },
    ("relay", "seedream-5.0"): {
        "image_generate": True,
        "image_translate": True,
    },
    ("relay", "seedream-4.6"): {
        "image_generate": True,
    },
    ("relay", "z-image-turbo"): {
        "image_generate": True,
    },
    ("gemini", "*"): {
        "image_generate": True,
        "image_translate": True,
        "image_analysis": True,
        "title_from_image": True,
        "text_generation": True,
    },
}


def get_model_capabilities(provider: str, model: str) -> dict:
    provider_key = str(provider or "").strip().lower()
    model_key = str(model or "").strip()
    result = dict(DEFAULT_CAPABILITIES)
    wildcard = CAPABILITY_MATRIX.get((provider_key, "*"), {})
    result.update(wildcard)
    result.update(CAPABILITY_MATRIX.get((provider_key, model_key), {}))
    return result


def model_supports(provider: str, model: str, capability: str) -> bool:
    return bool(get_model_capabilities(provider, model).get(capability, False))


def get_translation_provider_message(provider: str, model: str) -> str:
    if model_supports(provider, model, "image_translate"):
        return "当前模型支持图片翻译出图。"
    return f"当前模型 `{model}` 不支持图片翻译出图，请切换到支持该能力的模型（建议 `seedream-5.0`）。"
