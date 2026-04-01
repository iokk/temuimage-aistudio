from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

import requests
from PIL import Image

from temu_core.relay_text_client import RelayTextClient


def _clean_lines(text: str) -> list[str]:
    lines = [line.strip() for line in str(text or "").split("\n") if line.strip()]
    clean_lines: list[str] = []
    for line in lines:
        cleaned = re.sub(
            r"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|English[:]\s*|Chinese[:]\s*|中文[:]\s*)",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            clean_lines.append(cleaned)
    return clean_lines


def image_to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def image_from_data_url(data_url: str) -> Image.Image:
    raw = str(data_url or "").strip()
    if not raw.startswith("data:image/"):
        raise ValueError("Unsupported image data URL")
    _, encoded = raw.split(",", 1)
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


class GeminiTextClient:
    def __init__(self, api_key: str, model: str, timeout_ms: int = 180000):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_ms = timeout_ms
        self.last_error = ""
        self.total_tokens = 0

        if not self.api_key:
            raise ValueError("当前未配置 Gemini API Key")

        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=self.api_key)

    def get_last_error(self) -> str:
        return self.last_error

    def get_tokens_used(self) -> int:
        return self.total_tokens

    def _count_tokens(self, response: Any) -> None:
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return
        self.total_tokens += int(getattr(usage_metadata, "total_token_count", 0) or 0)

    def _generate_text(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model,
            contents=[prompt],
            config=self._types.GenerateContentConfig(response_modalities=["TEXT"]),
        )
        self._count_tokens(response)
        return str(getattr(response, "text", "") or "").strip()

    def generate_text(self, refs, prompt: str, max_tokens: int = 1800) -> str:
        del max_tokens
        contents: list[Any] = [prompt]
        contents.extend(list(refs or [])[:5])
        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self._types.GenerateContentConfig(response_modalities=["TEXT"]),
        )
        self._count_tokens(response)
        return str(getattr(response, "text", "") or "").strip()

    def generate_titles(self, product_info: str, template_prompt: str) -> list[str]:
        prompt = template_prompt.replace(
            "{product_info}", str(product_info or "").strip()
        )
        try:
            return _clean_lines(self._generate_text(prompt))
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return []

    def extract_text_from_image(
        self, image, source_lang: str = "auto"
    ) -> dict[str, Any]:
        prompt = (
            f"Extract visible text from this image. Source language hint: {source_lang}. "
            'Return JSON only: {"language":"detected language","lines":["line1","line2"]}'
        )
        try:
            text = self.generate_text([image], prompt)
            parsed = json.loads(text)
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return {"language": source_lang, "lines": []}
        if not isinstance(parsed, dict):
            return {"language": source_lang, "lines": []}
        return {
            "language": parsed.get("language") or source_lang,
            "lines": [
                str(line).strip()
                for line in (parsed.get("lines") or [])
                if str(line).strip()
            ],
        }

    def translate_lines(
        self,
        lines,
        source_lang: str = "auto",
        target_lang: str = "English",
        style_hint: str = "Literal",
        avoid_terms=None,
        enforce_english: bool = False,
        max_attempts: int = 1,
    ) -> list[str]:
        del max_attempts
        clean_lines = [str(line).strip() for line in (lines or []) if str(line).strip()]
        if not clean_lines:
            return []
        avoid_terms_text = ", ".join(avoid_terms or []) or "None"
        prompt = (
            f"Translate the following text lines from {source_lang} to {target_lang}.\n"
            f"Style: {style_hint}.\n"
            f"Avoid these terms if needed: {avoid_terms_text}.\n"
            f"English only required: {'yes' if enforce_english else 'no'}.\n"
            'Return JSON only: {"translated_lines":["line1","line2"]}\n'
            + "\n".join(clean_lines)
        )
        try:
            text = self.generate_text([], prompt)
            parsed = json.loads(text)
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return []
        translated = parsed.get("translated_lines") if isinstance(parsed, dict) else []
        return [str(line).strip() for line in (translated or []) if str(line).strip()]

    def extract_and_translate_image_text(
        self,
        image,
        source_lang: str = "auto",
        target_lang: str = "English",
        style_hint: str = "Literal",
        avoid_terms=None,
        enforce_english: bool = False,
        max_attempts: int = 1,
    ) -> dict[str, Any]:
        del max_attempts
        avoid_terms_text = ", ".join(avoid_terms or []) or "None"
        prompt = (
            f"Extract text from this image and translate it from {source_lang} to {target_lang}.\n"
            f"Style: {style_hint}.\n"
            f"Avoid these terms if needed: {avoid_terms_text}.\n"
            f"English only required: {'yes' if enforce_english else 'no'}.\n"
            'Return JSON only: {"language":"detected language","source_lines":["line1"],"translated_lines":["line1"]}'
        )
        try:
            text = self.generate_text([image], prompt)
            parsed = json.loads(text)
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return {"language": source_lang, "source_lines": [], "translated_lines": []}
        if not isinstance(parsed, dict):
            return {"language": source_lang, "source_lines": [], "translated_lines": []}
        return {
            "language": parsed.get("language") or source_lang,
            "source_lines": [
                str(line).strip()
                for line in (parsed.get("source_lines") or [])
                if str(line).strip()
            ],
            "translated_lines": [
                str(line).strip()
                for line in (parsed.get("translated_lines") or [])
                if str(line).strip()
            ],
        }


class GeminiImageClient:
    def __init__(self, api_key: str, model: str, timeout_ms: int = 180000):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_ms = timeout_ms
        self.last_error = ""
        self.total_tokens = 0

        if not self.api_key:
            raise ValueError("当前未配置 Gemini API Key")

        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=self.api_key)

    def get_last_error(self) -> str:
        return self.last_error

    def get_tokens_used(self) -> int:
        return self.total_tokens

    def _count_tokens(self, response: Any) -> None:
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return
        self.total_tokens += int(getattr(usage_metadata, "total_token_count", 0) or 0)

    def generate_image(
        self,
        refs,
        prompt: str,
        aspect: str = "1:1",
        size: str = "1K",
        thinking_level: str = "minimal",
        enforce_english: bool = False,
        max_attempts: int = 1,
    ):
        del size, thinking_level, enforce_english, max_attempts
        try:
            contents: list[Any] = [prompt]
            contents.extend(list(refs or [])[:5])
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=self._types.ImageConfig(aspect_ratio=aspect),
                ),
            )
            self._count_tokens(response)
            candidates = getattr(response, "candidates", None) or []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None):
                        return Image.open(io.BytesIO(inline_data.data))
            self.last_error = "API返回无图片数据"
            return None
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return None

    def translate_image(
        self,
        image,
        translated_lines,
        *,
        source_lines=None,
        preserve_ratio: bool = True,
        size: str = "1K",
        remove_overlay_text: bool = True,
    ):
        translated_text = "\n".join(
            [
                str(line).strip()
                for line in (translated_lines or [])
                if str(line).strip()
            ]
        )
        source_text = "\n".join(
            [str(line).strip() for line in (source_lines or []) if str(line).strip()]
        )
        ratio_text = (
            "preserve original ratio" if preserve_ratio else "use 1:1 square ratio"
        )
        cleanup_text = (
            "Remove decorative original-language overlays before rendering translated text."
            if remove_overlay_text
            else "Keep visible decorative overlays if needed."
        )
        prompt = (
            "Generate a translated ecommerce image based on the uploaded source image. "
            f"Replace the visible text with this English text:\n{translated_text or 'English translation unavailable'}\n\n"
            f"Original extracted text:\n{source_text or 'No OCR text returned'}\n\n"
            f"Layout rule: {ratio_text}. Output size: {size}. {cleanup_text} "
            "Keep the original composition, typography intent, colors, and product focus as much as possible. English only."
        )
        return self.generate_image([image], prompt, aspect="1:1", size=size)


class RelayImageClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_sec: int = 180,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.base_url = str(base_url or "").rstrip("/")
        self.timeout_sec = timeout_sec
        self.last_error = ""
        self.total_tokens = 0

        if not self.api_key:
            raise ValueError("当前未配置系统中转站 Key")
        if not self.base_url:
            raise ValueError("当前未配置系统中转站 API Base")

    def get_last_error(self) -> str:
        return self.last_error

    def get_tokens_used(self) -> int:
        return self.total_tokens

    def _extract_image_from_response(self, payload: dict[str, Any]):
        for item in payload.get("data", []) or []:
            if item.get("b64_json"):
                return Image.open(io.BytesIO(base64.b64decode(item["b64_json"])))
            if item.get("url"):
                response = requests.get(item["url"], timeout=60)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content))
        return None

    def generate_image(
        self,
        refs,
        prompt: str,
        aspect: str = "1:1",
        size: str = "1K",
        thinking_level: str = "minimal",
        enforce_english: bool = False,
        max_attempts: int = 1,
    ):
        del size, thinking_level, enforce_english, max_attempts
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": f"{prompt}\nOutput requirement: generate one ecommerce image in aspect ratio {aspect}. Use English only.",
            }
        ]
        for ref in list(refs or [])[:5]:
            try:
                buffer = io.BytesIO()
                ref.copy().save(buffer, format="PNG", optimize=True)
                encoded = base64.b64encode(buffer.getvalue()).decode()
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    }
                )
            except Exception:
                continue
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_sec,
            )
            text = response.text
            if response.status_code >= 400:
                self.last_error = text
                return None
            data = response.json()
            usage = data.get("usage", {}) or {}
            self.total_tokens += int(usage.get("total_tokens") or 0)
            image = self._extract_image_from_response(data)
            if image is None:
                self.last_error = text[:300]
            return image
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return None

    def generate_titles_from_image(
        self, images, product_info: str = "", template_prompt: str = ""
    ) -> list[str]:
        del images
        return self.generate_titles(product_info, template_prompt)

    def generate_titles(self, product_info: str, template_prompt: str) -> list[str]:
        prompt = template_prompt.replace("{product_info}", product_info)
        text = RelayTextClient(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            timeout_sec=self.timeout_sec,
        ).generate_text([], prompt, max_tokens=1200)
        return _clean_lines(text)

    def translate_lines(
        self,
        lines,
        source_lang: str = "auto",
        target_lang: str = "English",
        style_hint: str = "Literal",
        avoid_terms=None,
        enforce_english: bool = False,
        max_attempts: int = 1,
    ) -> list[str]:
        del max_attempts
        clean_lines = [str(line).strip() for line in (lines or []) if str(line).strip()]
        if not clean_lines:
            return []

        avoid_terms_text = ", ".join(avoid_terms or []) or "None"
        prompt = (
            f"Translate the following text lines from {source_lang} to {target_lang}.\n"
            f"Style: {style_hint}.\n"
            f"Avoid these terms if needed: {avoid_terms_text}.\n"
            f"English only required: {'yes' if enforce_english else 'no'}.\n"
            'Return JSON only: {"translated_lines":["line1","line2"]}\n'
            + "\n".join(clean_lines)
        )
        try:
            text = RelayTextClient(
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
                timeout_sec=self.timeout_sec,
            ).generate_text([], prompt, max_tokens=1200)
            parsed = json.loads(text)
            translated = (
                parsed.get("translated_lines") if isinstance(parsed, dict) else []
            )
            return [
                str(line).strip() for line in (translated or []) if str(line).strip()
            ]
        except Exception as exc:  # pragma: no cover - runtime path
            self.last_error = str(exc)
            return []

    def translate_image(
        self,
        image,
        translated_lines,
        *,
        source_lines=None,
        preserve_ratio: bool = True,
        size: str = "1K",
        remove_overlay_text: bool = True,
    ):
        translated_text = "\n".join(
            [
                str(line).strip()
                for line in (translated_lines or [])
                if str(line).strip()
            ]
        )
        source_text = "\n".join(
            [str(line).strip() for line in (source_lines or []) if str(line).strip()]
        )
        ratio_text = (
            "preserve original ratio" if preserve_ratio else "use 1:1 square ratio"
        )
        cleanup_text = (
            "Remove decorative original-language overlays before rendering translated text."
            if remove_overlay_text
            else "Keep visible decorative overlays if needed."
        )
        prompt = (
            "Generate a translated ecommerce image based on the uploaded source image. "
            f"Replace the visible text with this English text:\n{translated_text or 'English translation unavailable'}\n\n"
            f"Original extracted text:\n{source_text or 'No OCR text returned'}\n\n"
            f"Layout rule: {ratio_text}. Output size: {size}. {cleanup_text} "
            "Keep the original composition, typography intent, colors, and product focus as much as possible. English only."
        )
        return self.generate_image([image], prompt, aspect="1:1", size=size)


def build_text_client(
    *,
    provider: str,
    model: str,
    gemini_api_key: str,
    relay_api_key: str,
    relay_api_base: str,
):
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "relay":
        if not str(relay_api_key or "").strip():
            raise ValueError("当前未配置系统中转站 Key")
        if not str(relay_api_base or "").strip():
            raise ValueError("当前未配置系统中转站 API Base")
        return RelayTextClient(
            api_key=relay_api_key,
            model=model,
            base_url=relay_api_base,
        )

    return GeminiTextClient(api_key=gemini_api_key, model=model)


def build_image_client(
    *,
    provider: str,
    model: str,
    gemini_api_key: str,
    relay_api_key: str,
    relay_api_base: str,
):
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "relay":
        return RelayImageClient(
            api_key=relay_api_key,
            model=model,
            base_url=relay_api_base,
        )

    return GeminiImageClient(api_key=gemini_api_key, model=model)
