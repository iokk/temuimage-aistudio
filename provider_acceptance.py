"""Secret-safe provider capability checks used by release acceptance."""

from __future__ import annotations

import copy
import html
import io
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

from PIL import Image


ACCEPTANCE_PROMPT = (
    "A simple red ceramic mug centered on a white studio background, "
    "soft shadow, no text, square product photograph."
)


def redact_acceptance_error(message: str, secrets: Iterable[str] = ()) -> str:
    """Return a bounded error without credentials or upstream markup."""

    redacted = html.unescape(str(message or ""))
    redacted = re.sub(r"<[^>]*>", " ", redacted)

    def redact_url(match):
        try:
            parsed = urlsplit(match.group(0))
            hostname = parsed.hostname
            parsed.port
        except ValueError:
            return "[REDACTED_URL]"
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            return "[REDACTED_URL]"
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

    redacted = re.sub(r"https?://[^\s<>\"']+", redact_url, redacted)
    redacted = re.sub(
        r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]+",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(r"(?i)\bsk-[A-Za-z0-9_-]{8,}", "[REDACTED]", redacted)
    redacted = re.sub(
        r"(?i)(api[-_ ]?key\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
    )
    for secret in secrets:
        if secret:
            redacted = redacted.replace(str(secret), "[REDACTED]")
    redacted = re.sub(r"\s+", " ", redacted).strip()
    return redacted[:180] or "请求失败"


def _safe_error(application, error: Exception, secret: str = "") -> str:
    try:
        message = application.sanitize_task_error(str(error))
    except Exception:
        message = str(error)
    return redact_acceptance_error(message, (secret,))


def _safe_base_url(value: str) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    try:
        parsed = urlsplit(raw_value)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return ""
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _skipped(reason: str) -> dict:
    return {"requested": False, "ok": None, "reason": reason}


def _image_has_variation(image: Image.Image) -> bool:
    sample = image.convert("RGB")
    sample.thumbnail((64, 64))
    colors = sample.getcolors(maxcolors=max(1, sample.width * sample.height))
    return colors is None or len(colors) > 1


def verify_provider(
    provider: dict,
    application,
    include_responses: bool = True,
    include_live_image: bool = False,
    image_output: Optional[Path] = None,
) -> dict:
    """Verify requested provider capabilities without returning its secret."""

    provider = copy.deepcopy(provider or {})
    provider_type = str(provider.get("provider_type") or "gemini").lower()
    image_model = str(provider.get("image_model") or "")
    report = {
        "provider": {
            "id": str(provider.get("id") or ""),
            "name": str(provider.get("name") or ""),
            "provider_type": provider_type,
            "base_url": _safe_base_url(provider.get("base_url") or ""),
            "image_model": image_model,
            "title_model": str(provider.get("title_model") or ""),
        },
        "checks": {},
        "ok": False,
    }

    secret = ""
    try:
        secret = str(application.resolve_provider_api_key(provider) or "")
    except Exception as error:
        report["checks"]["credentials"] = {
            "requested": True,
            "ok": False,
            "configured": False,
            "error": _safe_error(application, error, secret),
        }
        secret = ""
    else:
        report["checks"]["credentials"] = {
            "requested": True,
            "ok": bool(secret),
            "configured": bool(secret),
        }

    if not secret:
        missing = "未配置可用的 API Key"
        for name in ("models", "text"):
            report["checks"][name] = {
                "requested": True,
                "ok": False,
                "error": missing,
            }
        report["checks"]["responses"] = (
            {"requested": True, "ok": False, "error": missing}
            if include_responses and provider_type == "openai"
            else _skipped("当前协议未请求 Responses 检查")
        )
        report["checks"]["image"] = (
            {"requested": True, "ok": False, "error": missing}
            if include_live_image
            else _skipped("未启用付费图片检查")
        )
        return report

    provider_for_calls = copy.deepcopy(provider)
    provider_for_calls["api_key"] = secret
    provider_for_calls["secret_storage"] = "runtime"

    try:
        catalog = application.fetch_provider_models(provider_for_calls)
        model_ids = {
            str(item.get("id") or "") for item in catalog if isinstance(item, dict)
        }
        configured_image_model_present = not image_model or image_model in model_ids
        report["checks"]["models"] = {
            "requested": True,
            "ok": bool(catalog) and configured_image_model_present,
            "count": len(catalog),
            "configured_image_model_present": configured_image_model_present,
        }
    except Exception as error:
        report["checks"]["models"] = {
            "requested": True,
            "ok": False,
            "error": _safe_error(application, error, secret),
        }

    client = None
    try:
        client = application.create_ai_client(provider_for_calls)
        reply = client.test_connection()
        report["checks"]["text"] = {
            "requested": True,
            "ok": bool(str(reply or "").strip()),
            "reply_nonempty": bool(str(reply or "").strip()),
        }
    except Exception as error:
        report["checks"]["text"] = {
            "requested": True,
            "ok": False,
            "error": _safe_error(application, error, secret),
        }

    responses_requested = include_responses and provider_type == "openai"
    if responses_requested:
        try:
            if client is None:
                client = application.create_ai_client(provider_for_calls)
            response = client._openai_call(
                "/responses",
                {
                    "model": provider.get("title_model") or "gpt-4o-mini",
                    "input": "Reply exactly OK.",
                    "max_output_tokens": 16,
                },
                timeout_seconds=90,
                retries=1,
            )
            response = response if isinstance(response, dict) else {}
            has_output = bool(response.get("output") or response.get("output_text"))
            raw_object = str(response.get("object") or "")
            raw_status = str(response.get("status") or "")
            safe_object = (
                redact_acceptance_error(raw_object, (secret,))
                if raw_object
                else ""
            )
            safe_status = (
                redact_acceptance_error(raw_status, (secret,))
                if raw_status
                else ""
            )
            report["checks"]["responses"] = {
                "requested": True,
                "ok": bool(response)
                and has_output
                and raw_status in ("", "completed"),
                "object": safe_object,
                "status": safe_status,
                "has_output": has_output,
            }
        except Exception as error:
            report["checks"]["responses"] = {
                "requested": True,
                "ok": False,
                "error": _safe_error(application, error, secret),
            }
    else:
        report["checks"]["responses"] = _skipped(
            "当前协议未请求 Responses 检查"
        )

    if include_live_image:
        try:
            if client is None:
                client = application.create_ai_client(provider_for_calls)
            image = client.generate_image(
                [], ACCEPTANCE_PROMPT, "1:1", "1K", "high", "zh"
            )
            if not isinstance(image, Image.Image):
                raise RuntimeError("上游未返回可解码图片")
            image.load()
            if not _image_has_variation(image):
                raise RuntimeError("上游返回图片缺少有效像素变化")
            encoded = io.BytesIO()
            image.save(encoded, format="PNG")
            if len(encoded.getvalue()) <= 100:
                raise RuntimeError("上游返回图片数据不完整")

            output = ""
            if image_output is not None:
                destination = Path(image_output)
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save(destination, format="PNG")
                output = str(destination)
            report["checks"]["image"] = {
                "requested": True,
                "ok": True,
                "size": [image.width, image.height],
                "output": output,
            }
        except Exception as error:
            report["checks"]["image"] = {
                "requested": True,
                "ok": False,
                "error": _safe_error(application, error, secret),
            }
    else:
        report["checks"]["image"] = _skipped("未启用付费图片检查")

    requested_checks = [
        check
        for check in report["checks"].values()
        if check.get("requested") is True
    ]
    report["ok"] = bool(requested_checks) and all(
        check.get("ok") is True for check in requested_checks
    )
    return report
