from __future__ import annotations


def _clean(value: str) -> str:
    return str(value or "").strip()


def has_system_service_access(has_valid_gemini_key: bool, settings: dict) -> bool:
    if has_valid_gemini_key:
        return True
    relay_key = _clean(settings.get("relay_api_key", ""))
    relay_base = _clean(settings.get("relay_api_base", ""))
    return bool(relay_key and relay_base)


def resolve_relay_runtime_config(
    settings: dict,
    input_key: str,
    input_base: str,
    input_model: str,
):
    relay_key = _clean(input_key) or _clean(settings.get("relay_api_key", ""))
    relay_base = (
        _clean(input_base) or _clean(settings.get("relay_api_base", ""))
    ).rstrip("/")
    relay_model = _clean(input_model) or _clean(
        settings.get("relay_default_image_model", "")
    )
    return relay_key, relay_base, relay_model
