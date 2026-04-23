from pathlib import Path
import io

from google import genai
from google.genai import types
from PIL import Image


class SmartGenerationError(RuntimeError):
    pass


SMART_TYPES = {
    "S1": {
        "name": "卖点图",
        "desc": "突出核心优势，强调商品的主要卖点和强感知收益。",
        "hint": "Feature focused ecommerce banner, strong value proposition.",
    },
    "S2": {
        "name": "场景图",
        "desc": "展示商品在真实场景中的使用方式和氛围。",
        "hint": "Lifestyle scene with believable usage context.",
    },
    "S3": {
        "name": "细节图",
        "desc": "展示材质、纹理、结构和工艺细节。",
        "hint": "Macro product close-up with detail emphasis.",
    },
    "S4": {
        "name": "对比图",
        "desc": "用视觉对比方式体现商品优势和差异。",
        "hint": "Side-by-side comparison graphic with clear product advantage.",
    },
    "S5": {
        "name": "规格图",
        "desc": "用于表达尺寸、参数、规格和关键信息点。",
        "hint": "Specification card with clean infographic composition.",
    },
}

LANGUAGES = {
    "en": {"english_name": "English", "native_name": "English"},
    "zh": {"english_name": "Chinese", "native_name": "中文"},
    "ja": {"english_name": "Japanese", "native_name": "日本語"},
    "fr": {"english_name": "French", "native_name": "Français"},
    "es": {"english_name": "Spanish", "native_name": "Español"},
}


def get_target_language(code: str) -> dict:
    return LANGUAGES.get(code, LANGUAGES["en"])


def build_smart_prompt(
    *,
    product_name: str,
    product_detail: str,
    type_key: str,
    image_language: str,
) -> str:
    type_info = SMART_TYPES.get(type_key, SMART_TYPES["S1"])
    language = get_target_language(image_language)
    return (
        f"Create an ecommerce {type_info['name']} for the product.\n"
        f"Product name: {product_name}\n"
        f"Product detail: {product_detail or 'N/A'}\n"
        f"Creative direction: {type_info['desc']}\n"
        f"Style hint: {type_info['hint']}\n"
        f"If the image contains any text, all text must be in {language['english_name']} ({language['native_name']}) only.\n"
        "Keep the layout commercially strong, high-clarity, and optimized for ecommerce conversion."
    )


class SmartGenerator:
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        if not api_key:
            raise SmartGenerationError("API Key 未配置。")
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
        raise SmartGenerationError("API返回无图片数据")

    def generate_image(
        self,
        *,
        image_paths: list[str],
        product_name: str,
        product_detail: str,
        type_key: str,
        image_language: str,
        aspect_ratio: str,
    ) -> Image.Image:
        parts = self._prepare_reference_parts(image_paths)
        if not parts:
            raise SmartGenerationError("未提供可用参考图。")
        prompt = build_smart_prompt(
            product_name=product_name,
            product_detail=product_detail,
            type_key=type_key,
            image_language=image_language,
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
