import io
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image


class QuickGenerationError(RuntimeError):
    pass


LANGUAGES = {
    "en": {"english_name": "English", "native_name": "English"},
    "zh": {"english_name": "Chinese", "native_name": "中文"},
    "ja": {"english_name": "Japanese", "native_name": "日本語"},
    "fr": {"english_name": "French", "native_name": "Français"},
    "es": {"english_name": "Spanish", "native_name": "Español"},
}

QUICK_MODE_PROMPTS = {
    "hero": "Create a premium ecommerce hero image with strong product focus and clear visual hierarchy.",
    "feature": "Create a feature-focused ecommerce image that highlights a key benefit in a persuasive, modern layout.",
    "lifestyle": "Create a lifestyle ecommerce image that places the product in a believable, conversion-friendly context.",
}


def get_target_language(code: str) -> dict:
    return LANGUAGES.get(code, LANGUAGES["en"])


def build_quick_prompt(
    *,
    product_name: str,
    product_detail: str,
    quick_mode: str,
    output_language: str,
) -> str:
    language = get_target_language(output_language)
    mode_prompt = QUICK_MODE_PROMPTS.get(quick_mode, QUICK_MODE_PROMPTS["hero"])
    return (
        f"{mode_prompt}\n"
        f"Product name: {product_name}\n"
        f"Product detail: {product_detail or 'N/A'}\n"
        f"If the image contains text, all text must be in {language['english_name']} ({language['native_name']}) only.\n"
        "Keep the composition commercially useful for ecommerce and maintain high visual clarity."
    )


class QuickGenerator:
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        if not api_key:
            raise QuickGenerationError("API Key 未配置。")
        client_kwargs = {
            "api_key": api_key,
            "http_options": types.HttpOptions(timeout=120000, base_url=base_url or None),
        }
        self.client = genai.Client(**client_kwargs)
        self.model = model or "nano-banana"

    def _prepare_reference_parts(self, image_paths: list[str]) -> list[types.Part]:
        parts: list[types.Part] = []
        for image_path in image_paths[:5]:
            source = Path(image_path)
            if not source.exists():
                continue
            with Image.open(source) as image:
                normalized = image.convert("RGB")
                if max(normalized.size) > 1536:
                    normalized.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                normalized.save(buffer, format="PNG", optimize=True)
                parts.append(types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/png"))
        return parts

    def _extract_image(self, response) -> Image.Image:
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    return Image.open(io.BytesIO(part.inline_data.data))
        raise QuickGenerationError("API返回无图片数据")

    def generate_image(
        self,
        *,
        image_paths: list[str],
        product_name: str,
        product_detail: str,
        quick_mode: str,
        output_language: str,
        aspect_ratio: str,
    ) -> Image.Image:
        parts = self._prepare_reference_parts(image_paths)
        if not parts:
            raise QuickGenerationError("未提供可用参考图片。")

        prompt = build_quick_prompt(
            product_name=product_name,
            product_detail=product_detail,
            quick_mode=quick_mode,
            output_language=output_language,
        )
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=[*parts, prompt],
            config=config,
        )
        return self._extract_image(response)
