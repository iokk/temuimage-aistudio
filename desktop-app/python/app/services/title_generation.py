from dataclasses import dataclass
import io
import re
from typing import List

from google import genai
from google.genai import types
from PIL import Image


MIN_TITLE_EN_CHARS = 180
MAX_TITLE_EN_CHARS = 250

LANGUAGES = {
    "en": {"english_name": "English", "native_name": "English", "label": "英语"},
    "zh": {"english_name": "Chinese", "native_name": "中文", "label": "中文"},
    "ja": {"english_name": "Japanese", "native_name": "日本語", "label": "日语"},
    "vi": {"english_name": "Vietnamese", "native_name": "Tiếng Việt", "label": "越南语"},
    "th": {"english_name": "Thai", "native_name": "ไทย", "label": "泰语"},
    "fr": {"english_name": "French", "native_name": "Français", "label": "法语"},
    "es": {"english_name": "Spanish", "native_name": "Español", "label": "西班牙语"},
}

DEFAULT_TEMPLATE_PROMPT = (
    "You are writing ecommerce product titles. Product details: {product_info}. "
    "Generate three strong title strategies: search optimization, conversion optimization, "
    "and differentiation. English title length must stay within the required range."
)

TITLE_LINE_PREFIXES = [
    "English",
    "Chinese",
    "中文",
    "Japanese",
    "日语",
    "Vietnamese",
    "越南语",
    "Thai",
    "泰语",
    "French",
    "法语",
    "Spanish",
    "西班牙语",
    "Target Language",
    "Translation",
]


@dataclass
class TitleGenerationResult:
    success: bool
    titles: List[str]
    raw_text: str
    error_message: str = ""


class TitleGenerationError(RuntimeError):
    pass


def get_target_language(code: str) -> dict:
    return LANGUAGES.get(code, LANGUAGES["en"])


def build_title_prompt(template_prompt: str, product_info: str, target_language: str) -> str:
    lang = get_target_language(target_language)
    template = (template_prompt or DEFAULT_TEMPLATE_PROMPT).replace(
        "{product_info}", product_info
    )
    if target_language == "en":
        return (
            f"{template}\n\n"
            "TARGET LANGUAGE RULES\n"
            "- Output English only.\n"
            "- Generate exactly 3 English titles with no translation lines.\n"
            f"- Every English title must be {MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS} characters.\n"
            "- Output exactly 3 lines total with no labels or commentary."
        )

    return (
        f"{template}\n\n"
        "TARGET LANGUAGE RULES\n"
        "- Keep English as the fixed source language for every first line.\n"
        f"- The second line of each title must be in {lang['english_name']} ({lang['native_name']}).\n"
        "- Output exactly 6 lines total with no labels or commentary.\n"
        f"- Line order must be English line then {lang['english_name']} line, repeated 3 times."
    )


def parse_title_lines(text: str) -> list[str]:
    cleaned_text = (text or "").strip()
    if cleaned_text.startswith("```"):
        lines = cleaned_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned_text = "\n".join(lines).strip()

    lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]
    clean_lines = []
    line_prefix_pattern = "|".join(re.escape(prefix) for prefix in TITLE_LINE_PREFIXES)
    for line in lines:
        sanitized = re.sub(
            rf"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|(?:{line_prefix_pattern})[:：]\s*)",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()
        if sanitized:
            clean_lines.append(sanitized)
    return clean_lines


def validate_title_lines(lines: list[str], target_language: str) -> tuple[bool, str]:
    expected_lines = 3 if target_language == "en" else 6
    if len(lines) != expected_lines:
      return False, f"输出行数为{len(lines)}，需为{expected_lines}行"

    for index, line in enumerate(lines):
        if not line:
            return False, f"第{index + 1}行为空"
        if target_language == "en" or index % 2 == 0:
            line_length = len(line)
            if line_length < MIN_TITLE_EN_CHARS or line_length > MAX_TITLE_EN_CHARS:
                return (
                    False,
                    f"英文行长度不符合{MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS}字符要求",
                )

    return True, ""


class TitleGenerator:
    def __init__(
        self, api_key: str, title_model: str, vision_model: str = "", base_url: str = ""
    ):
        if not api_key:
            raise TitleGenerationError("API Key 未配置。")
        client_kwargs = {
            "api_key": api_key,
            "http_options": types.HttpOptions(timeout=60000, base_url=base_url or None),
        }
        self.client = genai.Client(**client_kwargs)
        self.title_model = title_model or "gemini-3.1-flash-lite-preview"
        self.vision_model = vision_model or title_model or "gemini-3.1-flash-lite-preview"

    def _prepare_images(self, image_paths: list[str]) -> list[types.Part]:
        parts: list[types.Part] = []
        for image_path in image_paths[:5]:
            try:
                with Image.open(image_path) as image:
                    normalized = image.convert("RGB")
                    if max(normalized.size) > 1024:
                        normalized.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    normalized.save(buffer, format="PNG", optimize=True)
                    parts.append(
                        types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/png")
                    )
            except OSError:
                continue
        return parts

    def generate_titles(
        self, product_info: str, template_prompt: str, target_language: str
    ) -> TitleGenerationResult:
        prompt = build_title_prompt(template_prompt, product_info, target_language)
        last_error = ""
        last_raw = ""

        for attempt in range(1, 3):
            prompt_text = prompt
            if attempt == 2:
                language = get_target_language(target_language)
                strict_suffix = (
                    "Return exactly 3 lines, English only, no extra commentary."
                    if target_language == "en"
                    else (
                        f"Return exactly 6 lines, English then {language['english_name']} for "
                        "each title, no extra commentary."
                    )
                )
                prompt_text = f"{prompt}\n\nSTRICT OUTPUT: {strict_suffix}"

            try:
                response = self.client.models.generate_content(
                    model=self.title_model,
                    contents=[prompt_text],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
                text = response.text.strip() if response.text else ""
                last_raw = text
                lines = parse_title_lines(text)
                valid, reason = validate_title_lines(lines, target_language)
                if valid:
                    return TitleGenerationResult(success=True, titles=lines, raw_text=text)
                last_error = reason
            except Exception as exc:
                last_error = str(exc)

        return TitleGenerationResult(
            success=False,
            titles=[],
            raw_text=last_raw,
            error_message=last_error or "标题生成失败",
        )

    def generate_titles_from_images(
        self,
        image_paths: list[str],
        product_info: str,
        template_prompt: str,
        target_language: str,
    ) -> TitleGenerationResult:
        image_parts = self._prepare_images(image_paths)
        if not image_parts:
            raise TitleGenerationError("未提供可用图片。")

        prompt = build_title_prompt(
            template_prompt,
            product_info or "Analyze the uploaded product images and infer the product details.",
            target_language,
        )
        last_error = ""
        last_raw = ""

        for attempt in range(1, 3):
            prompt_text = prompt
            if attempt == 2:
                language = get_target_language(target_language)
                strict_suffix = (
                    "Return exactly 3 lines, English only, no extra commentary."
                    if target_language == "en"
                    else (
                        f"Return exactly 6 lines, English then {language['english_name']} for "
                        "each title, no extra commentary."
                    )
                )
                prompt_text = f"{prompt}\n\nSTRICT OUTPUT: {strict_suffix}"

            try:
                response = self.client.models.generate_content(
                    model=self.vision_model,
                    contents=[*image_parts, prompt_text],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
                text = response.text.strip() if response.text else ""
                last_raw = text
                lines = parse_title_lines(text)
                valid, reason = validate_title_lines(lines, target_language)
                if valid:
                    return TitleGenerationResult(success=True, titles=lines, raw_text=text)
                last_error = reason
            except Exception as exc:
                last_error = str(exc)

        return TitleGenerationResult(
            success=False,
            titles=[],
            raw_text=last_raw,
            error_message=last_error or "图片标题生成失败",
        )
