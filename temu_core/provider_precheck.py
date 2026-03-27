from __future__ import annotations

from temu_core.provider_capabilities import model_supports


CAPABILITY_LABELS = {
    "image_generate": "图片生成",
    "image_translate": "图片翻译出图",
    "image_analysis": "图片分析",
    "title_from_image": "图片标题生成",
    "text_generation": "文本生成",
}


def validate_relay_models(
    provider: str,
    relay_base: str,
    relay_key: str,
    image_model: str,
    analysis_model: str,
    required_capabilities: list,
    probe_func,
):
    if str(provider or "").lower() != "relay":
        return []
    reasons = []
    if not str(relay_key or "").strip():
        return ["当前未配置可用的中转站 Key"]
    probed = {}

    for capability in required_capabilities:
        target_model = (
            analysis_model
            if capability in {"image_analysis", "title_from_image", "text_generation"}
            else image_model
        )
        if not model_supports("relay", target_model, capability):
            reasons.append(
                f"当前模型 `{target_model}` 不支持{CAPABILITY_LABELS.get(capability, capability)}"
            )
            continue
        if target_model not in probed:
            probed[target_model] = probe_func(
                relay_base, relay_key, target_model, capability
            )
        ok, msg = probed[target_model]
        if not ok:
            reasons.append(f"当前模型 `{target_model}` 通道不可用：{msg}")
    seen = []
    for reason in reasons:
        if reason not in seen:
            seen.append(reason)
    return seen


def describe_capability_reasons(
    provider: str,
    image_model: str,
    analysis_model: str,
    required_capabilities: list,
):
    if str(provider or "").lower() != "relay":
        return []
    reasons = []
    for capability in required_capabilities:
        target_model = (
            analysis_model
            if capability in {"image_analysis", "title_from_image", "text_generation"}
            else image_model
        )
        if not model_supports("relay", target_model, capability):
            reasons.append(
                f"当前模型 `{target_model}` 不支持{CAPABILITY_LABELS.get(capability, capability)}"
            )
    return reasons
