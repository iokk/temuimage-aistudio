from __future__ import annotations


def _clean(value: str) -> str:
    return str(value or "").strip()


def resolve_runtime_credentials(
    preferred_provider: str,
    use_own_credentials: bool,
    own_provider: str,
    own_gemini_key: str,
    own_relay_key: str,
    own_relay_base: str,
    own_relay_model: str,
    system_gemini_key: str,
    system_relay_key: str,
    system_relay_base: str,
    system_relay_model: str,
):
    provider = _clean(preferred_provider).lower() or "gemini"
    if use_own_credentials:
        selected_own_provider = _clean(own_provider).lower() or provider
        if selected_own_provider == "relay":
            return {
                "provider": "relay",
                "scope": "user",
                "api_key": _clean(own_relay_key),
                "base_url": _clean(own_relay_base).rstrip("/"),
                "model": _clean(own_relay_model),
            }
        return {
            "provider": "gemini",
            "scope": "user",
            "api_key": _clean(own_gemini_key),
            "base_url": "",
            "model": "",
        }

    if provider == "relay":
        return {
            "provider": "relay",
            "scope": "system",
            "api_key": _clean(system_relay_key),
            "base_url": _clean(system_relay_base).rstrip("/"),
            "model": _clean(system_relay_model),
        }
    return {
        "provider": "gemini",
        "scope": "system",
        "api_key": _clean(system_gemini_key),
        "base_url": "",
        "model": "",
    }


def select_translation_gemini_key(
    use_own_credentials: bool,
    own_provider: str,
    own_gemini_key: str,
    system_gemini_key: str,
) -> str:
    if use_own_credentials and _clean(own_provider).lower() == "gemini":
        return _clean(own_gemini_key)
    return _clean(system_gemini_key)
