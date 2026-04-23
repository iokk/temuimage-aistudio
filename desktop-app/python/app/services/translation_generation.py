import io
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image


class ImageTranslationError(RuntimeError):
    pass


LANGUAGES = {
    "en": {"english_name": "English", "native_name": "English"},
    "zh": {"english_name": "Chinese", "native_name": "中文"},
    "ja": {"english_name": "Japanese", "native_name": "日本語"},
    "vi": {"english_name": "Vietnamese", "native_name": "Tiếng Việt"},
    "th": {"english_name": "Thai", "native_name": "ไทย"},
    "fr": {"english_name": "French", "native_name": "Français"},
    "es": {"english_name": "Spanish", "native_name": "Español"},
}

DEFAULT_TRANSLATION_PROMPT = (
    "Translate this ecommerce image into {output_language_name} while preserving the original "
    "layout as much as possible.\n"
    "Goal: compliance-first translation, not creative redesign.\n"
    "Preserve the visual structure, product placement, composition, and spacing.\n"
    "Replace source text with natural {output_language_name} wording only.\n"
    "Avoid exaggerated claims and use platform-safe wording."
)


def get_target_language(code: str) -> dict:
    return LANGUAGES.get(code, LANGUAGES["en"])


def build_translation_prompt(target_language: str, compliance_mode: str) -> str:
    language = get_target_language(target_language)
    compliance_suffix = (
        "Strict compliance mode: if the source contains risky claims, replace them with safer alternatives."
        if compliance_mode == "strict"
        else "Standard compliance mode: keep the translation faithful and neutral."
    )
    return (
        DEFAULT_TRANSLATION_PROMPT.format(
            output_language_name=language["english_name"],
            output_language_native=language["native_name"],
        )
        + "\n"
        + compliance_suffix
    )


class ImageTranslator:
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        if not api_key:
            raise ImageTranslationError("API Key 未配置。")
        client_kwargs = {
            "api_key": api_key,
            "http_options": types.HttpOptions(timeout=120000, base_url=base_url or None),
        }
        self.client = genai.Client(**client_kwargs)
        self.model = model or "nano-banana"

    def _prepare_image_part(self, image_path: str) -> types.Part:
        source = Path(image_path)
        if not source.exists():
            raise ImageTranslationError(f"图片不存在：{image_path}")
        with Image.open(source) as image:
            normalized = image.convert("RGB")
            if max(normalized.size) > 1536:
                normalized.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            normalized.save(buffer, format="PNG", optimize=True)
            return types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/png")

    def _extract_image(self, response) -> Image.Image:
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    return Image.open(io.BytesIO(part.inline_data.data))
        raise ImageTranslationError("API返回无图片数据")

    def translate_image(
        self,
        image_path: str,
        target_language: str,
        compliance_mode: str,
        aspect_ratio: str,
    ) -> Image.Image:
        prompt = build_translation_prompt(target_language, compliance_mode)
        image_part = self._prepare_image_part(image_path)
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=[image_part, prompt],
            config=config,
        )
        return self._extract_image(response)
