"""
TEMU AI Studio V1.0.0
Vertex Express + Nano Banana 2 image workflow
"""

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import hashlib
import zipfile
import random
import time
import base64
from datetime import datetime, date
from pathlib import Path
import requests
from google import genai
from google.genai import types
from temu_core.bootstrap import bootstrap_platform_runtime
from temu_core.db import session_scope
from temu_core.settings import database_enabled as platform_database_enabled
from temu_core.streamlit_admin import (
    render_billing_admin_tab,
    render_redeem_code_admin_tab,
)
from temu_core.usage import record_usage_event

# ==================== 配置常量 ====================
APP_VERSION = "V1.0.0"
APP_AUTHOR = "企鹅 & 小明"
APP_COMMERCIAL = "安得跨境 企鹅&Jerry nowdn.com"
APP_NAME = "TEMU AI Studio"

DATA_DIR = Path("/app/data") if os.path.exists("/app/data") else Path("./data")
DATA_DIR.mkdir(exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
USERS_FILE = DATA_DIR / "users.json"
STATS_FILE = DATA_DIR / "stats.json"
API_KEYS_FILE = DATA_DIR / "api_keys.json"
PROMPTS_FILE = DATA_DIR / "prompts.json"
COMPLIANCE_FILE = DATA_DIR / "compliance.json"
TEMPLATES_FILE = DATA_DIR / "templates.json"
TITLE_TEMPLATES_FILE = DATA_DIR / "title_templates.json"

# ==================== 硬性限制 ====================
MAX_IMAGES = 14
MAX_NAME_CHARS = 200
MAX_DETAIL_CHARS = 500
MAX_TAGS = 8
MAX_TYPE_COUNT = 3
MAX_TOTAL_IMAGES = 20
MAX_HEADLINE_CHARS = 40
MAX_SUBLINE_CHARS = 60
MAX_BADGE_CHARS = 20
MAX_RETRIES = 2
MAX_TITLE_INFO_CHARS = 1000

# 标题字符限制
MIN_TITLE_EN_CHARS = 180
MAX_TITLE_EN_CHARS = 250

# ==================== Gemini 3 模型配置 ====================
MODELS = {
    "gemini-2.5-flash-image": {
        "name": "🍌 Nano Banana 2",
        "resolutions": ["1K"],
        "max_refs": 5,
        "thinking_levels": ["minimal", "high"],
        "default_thinking": "minimal",
        "supports_thinking": True,
    }
}
PRIMARY_IMAGE_MODEL = "gemini-2.5-flash-image"
LEGACY_IMAGE_MODELS = {"gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"}
MODEL_NAME_NANO_BANANA_2 = MODELS[PRIMARY_IMAGE_MODEL]["name"]

RELAY_API_BASE = "https://newapi.aisonnet.org/v1"
RELAY_IMAGE_MODELS = {
    "z-image-turbo": {"name": "z-image-turbo"},
    "imagine_x_1": {"name": "imagine_x_1"},
    "hunyuan-image-3": {"name": "hunyuan-image-3"},
    "grok-imagine-image": {"name": "grok-imagine-image"},
}
RELAY_TEXT_MODELS = {
    "nano-banana-pro-reverse": {"name": "nano-banana-pro-reverse"},
}
RELAY_MODEL_STATUS = {
    "z-image-turbo": {
        "label": "当前无通道",
        "color": "#ff4d4f",
        "note": "实测返回 model_not_found / no available channel",
    },
    "imagine_x_1": {
        "label": "不稳定",
        "color": "#faad14",
        "note": "模型存在，但实测出现 generation_error / limited",
    },
    "hunyuan-image-3": {
        "label": "当前无通道",
        "color": "#ff4d4f",
        "note": "实测返回 model_not_found / no available channel",
    },
    "grok-imagine-image": {
        "label": "不稳定",
        "color": "#faad14",
        "note": "模型存在，但实测多次 generation_error",
    },
    "nano-banana-pro-reverse": {
        "label": "当前无通道",
        "color": "#ff4d4f",
        "note": "当前默认组下无可用通道",
    },
}

try:
    GEMINI_MAX_INFLIGHT = int(os.getenv("GEMINI_MAX_INFLIGHT", "3"))
except Exception:
    GEMINI_MAX_INFLIGHT = 3
GEMINI_MAX_INFLIGHT = max(1, min(8, GEMINI_MAX_INFLIGHT))
GEMINI_CALL_SEMAPHORE = threading.BoundedSemaphore(GEMINI_MAX_INFLIGHT)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_vertex_express_key(api_key: str) -> bool:
    key = str(api_key or "").strip()
    return key.startswith("AQ.")


def should_use_vertex_express(api_key: str = "") -> bool:
    if _env_flag("GOOGLE_GENAI_USE_VERTEXAI", False):
        return True
    return is_vertex_express_key(api_key)


def get_rate_limit_hint(api_key: str = ""):
    if should_use_vertex_express(api_key):
        return {
            "provider": "Vertex Express",
            "image_parallelism": 1,
            "text_parallelism": 2,
            "note": "图片请求建议低并发，速率限制按项目计，不按单个 Key 计。",
        }
    return {
        "provider": "Gemini API",
        "image_parallelism": 2,
        "text_parallelism": 2,
        "note": "建议控制中低并发，优先稳定成功率。",
    }


def create_genai_client(api_key: str, http_options=None):
    kwargs = {"api_key": api_key}
    if http_options is not None:
        kwargs["http_options"] = http_options
    if should_use_vertex_express(api_key):
        kwargs["vertexai"] = True
    return genai.Client(**kwargs)


ASPECT_RATIOS = [
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
]

THINKING_LEVEL_DESC = {
    "minimal": "🚀 极速 - 最低延迟",
    "low": "⚡ 快速 - 低延迟",
    "medium": "⚖️ 平衡 - 适合大多数任务",
    "high": "🧠 深度 - 最大推理深度",
}

LANGUAGE_OPTIONS = {
    "auto": "自动识别",
    "en": "English",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
}

LANGUAGE_PROMPT_NAMES = {
    "auto": "auto-detect",
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
}

# ==================== 默认配置 ====================
DEFAULT_SETTINGS = {
    "daily_limit_user": 100,
    "daily_limit_vip": 100,
    "default_model": PRIMARY_IMAGE_MODEL,
    "default_image_provider": "Gemini",
    "default_resolution": "1K",
    "default_aspect": "1:1",
    "default_thinking_level": "minimal",
    "user_password": "eee666",
    "admin_password": "joolhome@2023",
    "compliance_mode": "strict",
    "allow_user_passwordless_login": False,
    "file_storage_type": "local",
    "file_retention_days": 7,
    "file_storage_path": str(DATA_DIR / "files"),
    "s3_endpoint": "",
    "s3_bucket": "",
    "s3_region": "",
    "s3_access_key": "",
    "s3_secret_key": "",
    "s3_prefix": "temu-files/",
    "s3_presign_expires": 86400,
    # 图片翻译默认设置
    "translate_max_upload": 50,
    "translate_batch_size": 20,
    "translate_max_input": 200,
    "translate_max_file_mb": 7,
    "translate_allowed_formats": "png,jpg,jpeg,webp,heic,heif",
    "translate_default_output_mode": "生成翻译图片",
    "translate_default_size_strategy": "保留原比例",
    "translate_default_ratio": "1:1",
    "translate_default_ratio_method": "补边(白色)",
    "translate_default_resolution": "1K",
    "translate_default_compliance_template": "default",
    "translate_default_model": PRIMARY_IMAGE_MODEL,
    "translate_text_model": PRIMARY_IMAGE_MODEL,
    "translate_fast_text_mode": True,
    "translate_text_workers": 2,
    "translate_force_english_output": True,
    "translate_english_max_retries": 2,
    "translate_cleanup_chinese_overlay": True,
    "translate_bg_max_concurrent": 2,
    "relay_api_base": RELAY_API_BASE,
    "relay_default_image_model": "imagine_x_1",
    "enforce_english_text": False,
    "english_text_max_retries": 1,
}

DEFAULT_API_KEYS = {"keys": [], "current_index": 0}

DEFAULT_COMPLIANCE = {
    "presets": {
        "strict": {
            "name": "🔒 强合规",
            "blacklist": [
                "FDA",
                "CE",
                "ISO",
                "certified",
                "approved",
                "medical",
                "cure",
                "treat",
                "heal",
                "best",
                "perfect",
                "100%",
                "guarantee",
                "forever",
                "only",
                "No.1",
                "first",
                "authentic",
                "genuine",
                "official",
                "organic",
                "natural",
                "pure",
                "real",
            ],
            "enabled": True,
        },
        "standard": {
            "name": "🛡️ 标准",
            "blacklist": [
                "FDA",
                "CE",
                "ISO",
                "certified",
                "medical",
                "cure",
                "treat",
                "authentic",
                "official",
            ],
            "enabled": True,
        },
        "loose": {
            "name": "🎨 宽松",
            "blacklist": ["FDA", "CE", "medical", "cure"],
            "enabled": True,
        },
    },
    "custom_blacklist": [],
    "whitelist": [],
    "user_custom": {},
    "translate_templates": {
        "default": {
            "name": "默认合规词模板",
            "words": [
                "FDA",
                "CE",
                "ISO",
                "certified",
                "approved",
                "medical",
                "cure",
                "treat",
                "heal",
                "best",
                "perfect",
                "100%",
                "guarantee",
                "forever",
                "only",
                "No.1",
                "first",
                "authentic",
                "genuine",
                "official",
                "organic",
                "natural",
                "pure",
                "real",
            ],
            "enabled": True,
        }
    },
}

# ==================== 标题模板 - 中英双语版 ====================
DEFAULT_TITLE_TEMPLATES = {
    "default": {
        "name": "🎯 TEMU标准优化 (中英双语)",
        "desc": "完整规则，中英双语输出，英文180-250字符",
        "prompt": """ROLE You are an ecommerce title optimization expert for TEMU and similar marketplace search systems. Your job is to generate high exposure high clarity English product titles based ONLY on the product information I provide. Never invent features materials sizes certifications compatibility or quantities that are not explicitly given or clearly visible.

INPUT I will provide one of the following A Product text description and attributes B One image or multiple images C A mix of text and images

TASK Generate exactly three product titles for the same product. Each title must have BOTH English and Chinese versions. Each title must be different in keyword focus and conversion angle while staying truthful.

HARD OUTPUT RULES
1 Each title must have TWO lines: first line English, second line Chinese translation
2 English titles must be between 180 and 250 characters (CRITICAL - count carefully)
3 Output must be plain text only
4 Do not include any special symbols or punctuation at all. This means no vertical bar slash ampersand hash comma colon semicolon dash hyphen underscore parentheses brackets quotes plus sign equals sign period or emoji. Use letters numbers and spaces only
5 Do not output bullet points labels explanations or extra lines
6 Keep the first 50 characters of English title as the most important keywords
7 Avoid keyword repetition within a title
8 Do not include brand names model numbers or trademarks unless they are explicitly provided and allowed
9 Do not use meaningless terms such as Generic No Brand Best Cheap Hot Sale

TITLE LOGIC AND STRUCTURE Follow this priority order
A Quantity or pack size if known for example 1PC 3Pcs Set 5Pairs
B Core category keyword that users search for must appear early within the first 5 to 15 words
C Primary benefit or differentiator in natural ecommerce English
D Key specification if critical such as size capacity material compatibility
E Target user or scenario if applicable such as Women Kids Office Travel Gift

Create three variants with different focus
Title 1 Search first Use the most standard core category keyword plus common traffic keywords
Title 2 Conversion first Lead with the strongest benefit plus scenario or user
Title 3 Differentiation first Emphasize a unique angle such as set value design style seasonal usage compatibility

KEYWORD CHOICE RULES
1 Prefer category common words over niche jargon
2 Use specific names over vague ones Bad Phone Accessory Good Phone Lanyard Strap
3 If compatibility exists add Compatible with plus device family only when explicitly provided
4 If size capacity is provided include it near the core noun
5 If the product is seasonal or giftable you may add a relevant term only if it naturally fits the item

TRUTHFULNESS AND FALLBACKS
If any attribute is unknown do not guess it
If quantity is unknown do not add pack counts
If material is unknown do not claim stainless steel ceramic cotton etc
If compatibility is unknown do not name device models
If size is unknown do not add oz cm inch
If the product type is ambiguous choose the safest broad category word

LANGUAGE QUALITY
Use clear natural marketplace English
Use Title Case style capitalization for major words
No grammar errors
Chinese translation must be accurate and natural

OUTPUT FORMAT (exactly 6 lines, no labels):
[English Title 1 - 180-250 chars]
[中文标题1]
[English Title 2 - 180-250 chars]
[中文标题2]
[English Title 3 - 180-250 chars]
[中文标题3]

Product information:
{product_info}

NOW GENERATE the six lines.""",
        "enabled": True,
    },
    "simple": {
        "name": "⚡ 简洁高效 (中英双语)",
        "desc": "快速生成，中英双语",
        "prompt": """Generate 3 product titles for TEMU marketplace. Each title needs English and Chinese versions.

Product: {product_info}

Rules:
- English: 180-250 characters, plain text, letters numbers spaces only
- Chinese: accurate translation
- No symbols, no brand names unless provided
- No meaningless words like Best Cheap Hot
- Title Case capitalization

Output exactly 6 lines (English then Chinese for each):
[English Title 1]
[中文标题1]
[English Title 2]
[中文标题2]
[English Title 3]
[中文标题3]""",
        "enabled": True,
    },
    "detailed": {
        "name": "📝 详细规格 (中英双语)",
        "desc": "适合规格复杂的商品",
        "prompt": """You are a TEMU title expert. Create 3 bilingual titles.

Product details:
{product_info}

Requirements:
- English: 180-250 characters, plain text
- Chinese: natural translation
- Include specifications if provided
- No invented features
- Title Case capitalization

Focus areas:
Title 1: Category keyword + specs (搜索优化)
Title 2: Benefits + use case (转化优化)
Title 3: Unique features + target user (差异化)

Output exactly 6 lines:
[English Title 1]
[中文标题1]
[English Title 2]
[中文标题2]
[English Title 3]
[中文标题3]""",
        "enabled": True,
    },
    "image_analysis": {
        "name": "🖼️ 图片智能分析 (中英双语)",
        "desc": "根据商品图片AI分析生成双语标题",
        "prompt": """Analyze the product image(s) and generate 3 bilingual titles for TEMU marketplace.

Additional info: {product_info}

Based on what you see in the image:
1. Identify product category and type
2. Note visible features, materials, colors, design
3. Consider target customer and use cases

RULES:
- English: 180-250 characters, plain text, letters numbers spaces only
- Chinese: accurate natural translation
- Do NOT invent features not visible
- Do NOT include brand names unless clearly visible
- Title Case capitalization

Output exactly 6 lines:
[English Title 1]
[中文标题1]
[English Title 2]
[中文标题2]
[English Title 3]
[中文标题3]""",
        "enabled": True,
    },
}

DEFAULT_PROMPTS = {
    "anchor_analysis": """Analyze these product images and return JSON:
{"primary_category": "category", "product_name_en": "English name", "product_name_zh": "中文名", "visual_attrs": ["attr1", "attr2"], "confidence": 0.8}
Product name: {product_name}
Product detail: {product_detail}
Return valid JSON only. ALL text in English.""",
    "requirements_gen": """你是电商组图策划专家。基于商品信息生成中文图需。
商品: {product_name} ({category})
特征: {features}
标签: {tags}
需要类型: {types}
为每张图生成JSON数组:
[{{"type_key": "xxx", "type_name": "名称", "index": 1, "topic": "主题30字", "scene": "场景80字", "copy": "文案50字"}}]
规则: 不编造未提供信息, 不提认证/医疗/绝对化, 尺寸图标注用inch和cm, 返回有效JSON""",
    "en_copy_gen": """Generate English copy for product images.
Product: {product_name}
Category: {category}
Requirements: {requirements}
Generate JSON array:
[{{"type_key": "xxx", "index": 1, "headline": "max 40 chars", "subline": "max 60 chars", "badge": "max 20 chars or empty"}}]
CRITICAL: Simple American English ONLY. Letters numbers spaces ONLY. NO Chinese/Japanese/Korean characters. Return valid JSON.""",
    "image_prompt": """Professional ecommerce product image.
Product: {product_name}
Category: {category}
Image type: {image_type}
Style: {style_hint}
Scene: {scene}
Text overlay (ENGLISH ONLY):
{text_content}
CRITICAL: Product must match reference. ALL text MUST be ENGLISH only. NO Chinese/Japanese/Korean characters. Avoid any non-English glyphs. Professional ecommerce style.
Aspect ratio: {aspect_ratio}""",
    "size_image_prompt": """Professional product dimension diagram.
Product: {product_name}
Style: Clean technical illustration on white background
REQUIRED: Clear bidirectional arrow lines. Dual unit measurements: XX.XX inch / XX.X cm. Use word "inch" NOT "in". Clean sans-serif font. ALL text in ENGLISH only. NO Chinese/Japanese/Korean characters.
Aspect ratio: {aspect_ratio}""",
    "image_text_extract": """You are an OCR assistant for ecommerce images. Extract ALL visible text exactly as it appears.
Return JSON only in this format:
{{"language": "auto", "lines": ["line1", "line2"]}}
Rules:
- Keep line order top to bottom
- If no text, return {{"language":"auto","lines":[]}}
Source language hint: {source_lang}""",
    "image_text_translate": """You are a professional ecommerce translator for Amazon-style listings.
Translate each line to {target_lang} from {source_lang}. Preserve meaning and keep the same number of lines.
Style: {style_hint}
Avoid these compliance terms in output (if any): {avoid_terms}
CRITICAL:
- If target language is English, output must be natural US ecommerce English only
- No Chinese/Japanese/Korean characters in translated output
- Do not keep mixed bilingual text in one line
- Avoid prohibited absolute claims (best, no.1, guaranteed cure) unless explicitly required by policy-safe wording
Return JSON array of translated lines only.
Lines JSON: {lines_json}""",
    "image_text_extract_translate": """You are an OCR + translator for ecommerce images (Amazon style).
From the input image, first extract visible source text lines (top to bottom), then translate to {target_lang}.
Source language hint: {source_lang}
Style: {style_hint}
Avoid these compliance terms in output (if any): {avoid_terms}
Return JSON only in this exact format:
{{"language":"auto","source_lines":["line1","line2"],"translated_lines":["line1_t","line2_t"]}}
Rules:
- Keep order by visual reading sequence
- Keep source_lines and translated_lines aligned by index
- If target language is English, translated_lines must be US English only (no Chinese/Japanese/Korean characters)
- If no text, return empty arrays""",
    "image_translate_prompt": """You are given a reference ecommerce product image.
Translate all visible text from {source_lang} to {target_lang}.
Style: {style_hint}
Layout: {layout_hint}
Avoid these compliance terms in output (if any): {avoid_terms}
Rules:
- Preserve layout typography colors and all non text elements
- Remove non-product Chinese overlay text blocks corner labels and stamp-like decorative Chinese marks when they are not essential to product meaning
- For removed Chinese overlays, reconstruct a natural clean background in the same style
- Keep brand trademark certification logos and legally required product markings unchanged
- If a text segment is already in target language keep it
- If target language is English, all rendered text must be US English only with no Chinese/Japanese/Korean characters
- Use concise, policy-safe ecommerce wording suitable for Amazon and TEMU platform rules
Output image only.""",
}

DEFAULT_TEMPLATES = {
    "combo_types": {
        "main": {
            "name": "主图白底",
            "icon": "🎯",
            "desc": "纯白背景产品主图",
            "hint": "Pure white background, centered product",
            "enabled": True,
            "order": 1,
        },
        "feature": {
            "name": "功能卖点",
            "icon": "⭐",
            "desc": "核心功能展示图",
            "hint": "Feature highlights with callouts",
            "enabled": True,
            "order": 2,
        },
        "scene": {
            "name": "场景应用",
            "icon": "🏠",
            "desc": "使用场景展示",
            "hint": "Lifestyle scene, product in use",
            "enabled": True,
            "order": 3,
        },
        "detail": {
            "name": "细节特写",
            "icon": "🔍",
            "desc": "工艺细节放大",
            "hint": "Macro close-up shot, texture details",
            "enabled": True,
            "order": 4,
        },
        "size": {
            "name": "尺寸规格",
            "icon": "📐",
            "desc": "尺寸标注图",
            "hint": "Dimension diagram with inch/cm",
            "enabled": True,
            "order": 5,
            "special": True,
        },
        "compare": {
            "name": "对比优势",
            "icon": "⚖️",
            "desc": "竞品对比图",
            "hint": "Side by side comparison",
            "enabled": True,
            "order": 6,
        },
        "package": {
            "name": "清单展示",
            "icon": "📦",
            "desc": "包装内容物",
            "hint": "Flat lay of package contents",
            "enabled": True,
            "order": 7,
        },
        "steps": {
            "name": "使用步骤",
            "icon": "📋",
            "desc": "操作步骤图",
            "hint": "Step by step visual guide",
            "enabled": True,
            "order": 8,
        },
    },
    "smart_types": {
        "S1": {
            "name": "卖点图",
            "icon": "🌟",
            "desc": "突出核心优势",
            "enabled": True,
            "order": 1,
        },
        "S2": {
            "name": "场景图",
            "icon": "🏡",
            "desc": "展示使用场景",
            "enabled": True,
            "order": 2,
        },
        "S3": {
            "name": "细节图",
            "icon": "🔍",
            "desc": "展现工艺细节",
            "enabled": True,
            "order": 3,
        },
        "S4": {
            "name": "对比图",
            "icon": "⚖️",
            "desc": "对比产品优势",
            "enabled": True,
            "order": 4,
        },
        "S5": {
            "name": "规格图",
            "icon": "📐",
            "desc": "展示产品参数",
            "enabled": True,
            "order": 5,
        },
    },
}


# ==================== 数据管理 ====================
def load_json(fp, default=None):
    try:
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default.copy() if default else {}


def save_json(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on", "t"}:
            return True
        if v in {"0", "false", "no", "n", "off", "f"}:
            return False
    return default


def get_settings():
    s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    for k, v in DEFAULT_SETTINGS.items():
        if k not in s:
            s[k] = v
    if "translate_batch_size" not in s:
        s["translate_batch_size"] = s.get(
            "translate_max_upload", DEFAULT_SETTINGS.get("translate_batch_size", 20)
        )
    # 提升普通用户默认限额到100次（如原值更低）
    try:
        s["daily_limit_user"] = max(int(s.get("daily_limit_user", 100)), 100)
    except Exception:
        s["daily_limit_user"] = 100
    # 全局锁定出图模型为 Nano Banana 2
    s["default_model"] = PRIMARY_IMAGE_MODEL
    s["translate_default_model"] = PRIMARY_IMAGE_MODEL
    s["translate_text_model"] = PRIMARY_IMAGE_MODEL
    s["default_resolution"] = "1K"
    s["translate_default_resolution"] = "1K"
    if s.get("default_image_provider") not in ("Gemini", "中转站"):
        s["default_image_provider"] = "Gemini"
    s["relay_api_base"] = str(
        s.get("relay_api_base", RELAY_API_BASE) or RELAY_API_BASE
    ).rstrip("/")
    if s.get("relay_default_image_model") not in RELAY_IMAGE_MODELS:
        s["relay_default_image_model"] = "imagine_x_1"
    try:
        workers = int(
            s.get(
                "translate_text_workers",
                DEFAULT_SETTINGS.get("translate_text_workers", 2),
            )
        )
    except Exception:
        workers = DEFAULT_SETTINGS.get("translate_text_workers", 2)
    s["translate_text_workers"] = max(1, min(6, workers))
    s["translate_force_english_output"] = _to_bool(
        s.get(
            "translate_force_english_output",
            DEFAULT_SETTINGS.get("translate_force_english_output", True),
        ),
        True,
    )
    s["translate_cleanup_chinese_overlay"] = _to_bool(
        s.get(
            "translate_cleanup_chinese_overlay",
            DEFAULT_SETTINGS.get("translate_cleanup_chinese_overlay", True),
        ),
        True,
    )
    try:
        bg_workers = int(
            s.get(
                "translate_bg_max_concurrent",
                DEFAULT_SETTINGS.get("translate_bg_max_concurrent", 2),
            )
        )
    except Exception:
        bg_workers = DEFAULT_SETTINGS.get("translate_bg_max_concurrent", 2)
    s["translate_bg_max_concurrent"] = max(1, min(6, bg_workers))
    s["allow_user_passwordless_login"] = _to_bool(
        s.get(
            "allow_user_passwordless_login",
            DEFAULT_SETTINGS.get("allow_user_passwordless_login", False),
        ),
        False,
    )
    try:
        en_retries = int(
            s.get(
                "translate_english_max_retries",
                DEFAULT_SETTINGS.get("translate_english_max_retries", 2),
            )
        )
    except Exception:
        en_retries = DEFAULT_SETTINGS.get("translate_english_max_retries", 2)
    s["translate_english_max_retries"] = max(1, min(5, en_retries))
    return s


def save_settings(s):
    return save_json(SETTINGS_FILE, s)


def _normalize_api_keys_data(data):
    if data is None:
        return {"keys": [], "current_index": 0}
    if isinstance(data, list):
        data = {"keys": data, "current_index": 0}
    if not isinstance(data, dict):
        return {"keys": [], "current_index": 0}
    keys = data.get("keys", [])
    if isinstance(keys, list) and keys and all(isinstance(k, str) for k in keys):
        keys = [
            {"key": k.strip(), "enabled": True}
            for k in keys
            if isinstance(k, str) and k.strip()
        ]
    if isinstance(keys, list) and keys and all(isinstance(k, dict) for k in keys):
        cleaned = []
        for k in keys:
            kk = (k.get("key") or "").strip()
            if kk:
                cleaned.append({**k, "key": kk})
        keys = cleaned
    if not isinstance(keys, list):
        keys = []
    data["keys"] = keys
    if "current_index" not in data or not isinstance(data["current_index"], int):
        data["current_index"] = 0
    return data


def get_api_keys():
    data = load_json(API_KEYS_FILE, DEFAULT_API_KEYS)
    data = _normalize_api_keys_data(data)
    save_api_keys(data)
    return data


def _has_valid_system_key():
    keys_data = get_api_keys()
    keys = keys_data.get("keys", [])
    now = datetime.now().isoformat()
    valid = [
        k
        for k in keys
        if k.get("enabled", True) and (not k.get("expires") or k.get("expires") > now)
    ]
    return len(valid) > 0


def bootstrap_env_system_key():
    try:
        env_key = (
            os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        ).strip()
        if not env_key:
            return
        data = get_api_keys()
        if data.get("keys"):
            return
        data["keys"] = [{"key": env_key, "enabled": True}]
        data["current_index"] = 0
        save_api_keys(data)
    except Exception:
        return


def save_api_keys(data):
    return save_json(API_KEYS_FILE, data)


def _parse_env_bool(name):
    return _to_bool(os.getenv(name), default=None)


def _parse_fixed_keys(raw_text):
    if not raw_text:
        return []
    keys, seen = [], set()
    for item in re.split(r"[\n,;]+", raw_text):
        key = (item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _build_fixed_key_entries(keys):
    return [
        {"key": k, "name": f"Fixed-{i + 1}", "enabled": True}
        for i, k in enumerate(keys)
    ]


def _sync_fixed_api_keys_from_env():
    raw = (os.getenv("SYSTEM_API_KEYS_FIXED") or "").strip()
    fixed_keys = _parse_fixed_keys(raw)
    if not fixed_keys:
        return
    mode = (os.getenv("SYSTEM_API_KEYS_SYNC_MODE") or "if_empty").strip().lower()
    data = get_api_keys()
    current = data.get("keys", [])
    current_clean = [
        k for k in current if isinstance(k, dict) and (k.get("key") or "").strip()
    ]
    current_keys = [k.get("key", "").strip() for k in current_clean]
    changed = False

    if mode == "replace":
        target_entries = _build_fixed_key_entries(fixed_keys)
        if current_keys != fixed_keys:
            data["keys"] = target_entries
            data["current_index"] = 0
            changed = True
    elif mode == "merge":
        existing = set(current_keys)
        merged = list(current_clean)
        for i, key in enumerate(fixed_keys):
            if key in existing:
                continue
            merged.append({"key": key, "name": f"Fixed-{i + 1}", "enabled": True})
            changed = True
        if changed:
            data["keys"] = merged
            data["current_index"] = 0
    else:
        if not current_clean:
            data["keys"] = _build_fixed_key_entries(fixed_keys)
            data["current_index"] = 0
            changed = True

    if changed:
        save_api_keys(data)


def bootstrap_runtime_config():
    s = get_settings()
    changed = False

    admin_password_fixed = (os.getenv("ADMIN_PASSWORD_FIXED") or "").strip()
    if admin_password_fixed and s.get("admin_password") != admin_password_fixed:
        s["admin_password"] = admin_password_fixed
        changed = True

    user_password_fixed = (os.getenv("USER_PASSWORD_FIXED") or "").strip()
    if user_password_fixed and s.get("user_password") != user_password_fixed:
        s["user_password"] = user_password_fixed
        changed = True

    allow_passwordless = _parse_env_bool("ALLOW_PASSWORDLESS_USER_LOGIN")
    if (
        allow_passwordless is not None
        and s.get("allow_user_passwordless_login") != allow_passwordless
    ):
        s["allow_user_passwordless_login"] = allow_passwordless
        changed = True

    if changed:
        save_settings(s)

    _sync_fixed_api_keys_from_env()
    bootstrap_env_system_key()


def get_compliance():
    c = load_json(COMPLIANCE_FILE, DEFAULT_COMPLIANCE)
    for k, v in DEFAULT_COMPLIANCE.items():
        if k not in c:
            c[k] = v
    # 确保翻译合规模板结构完整
    if "translate_templates" not in c or not isinstance(
        c.get("translate_templates"), dict
    ):
        c["translate_templates"] = DEFAULT_COMPLIANCE.get(
            "translate_templates", {}
        ).copy()
    if "default" not in c["translate_templates"]:
        c["translate_templates"]["default"] = DEFAULT_COMPLIANCE["translate_templates"][
            "default"
        ].copy()
    return c


def save_compliance(data):
    return save_json(COMPLIANCE_FILE, data)


def get_prompts():
    p = load_json(PROMPTS_FILE, DEFAULT_PROMPTS)
    for k, v in DEFAULT_PROMPTS.items():
        if k not in p:
            p[k] = v
    return p


def save_prompts(data):
    return save_json(PROMPTS_FILE, data)


def get_templates():
    t = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
    for k, v in DEFAULT_TEMPLATES.items():
        if k not in t:
            t[k] = v
    return t


def save_templates(data):
    return save_json(TEMPLATES_FILE, data)


def get_title_templates():
    t = load_json(TITLE_TEMPLATES_FILE, DEFAULT_TITLE_TEMPLATES)
    for k, v in DEFAULT_TITLE_TEMPLATES.items():
        if k not in t:
            t[k] = v
    return t


def save_title_templates(data):
    return save_json(TITLE_TEMPLATES_FILE, data)


def get_next_api_key():
    keys_data = get_api_keys()
    keys = keys_data.get("keys", [])
    now = datetime.now().isoformat()
    valid = [
        k
        for k in keys
        if k.get("enabled", True) and (not k.get("expires") or k.get("expires") > now)
    ]
    if not valid:
        return None
    idx = keys_data.get("current_index", 0) % len(valid)
    keys_data["current_index"] = (idx + 1) % len(valid)
    save_api_keys(keys_data)
    return valid[idx].get("key")


def peek_system_api_key():
    keys_data = get_api_keys()
    keys = keys_data.get("keys", [])
    now = datetime.now().isoformat()
    valid = [
        k
        for k in keys
        if k.get("enabled", True) and (not k.get("expires") or k.get("expires") > now)
    ]
    if not valid:
        return ""
    return valid[0].get("key", "")


# ==================== 文件存储 ====================
def _get_storage_settings():
    s = get_settings()
    stype = (
        (os.getenv("FILE_STORAGE_TYPE") or s.get("file_storage_type") or "local")
        .strip()
        .lower()
    )
    retention = int(
        os.getenv("FILE_RETENTION_DAYS") or s.get("file_retention_days") or 7
    )
    base_path = (
        os.getenv("FILE_STORAGE_PATH")
        or s.get("file_storage_path")
        or "/app/data/files"
    )
    # 本地开发环境兼容：/app 不存在时回退到 ./data/files
    try:
        if str(base_path).startswith("/app/") and not Path(base_path).exists():
            base_path = str(DATA_DIR / "files")
    except Exception:
        pass
    return stype, retention, base_path, s


def _ensure_dir(p):
    try:
        Path(p).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _save_bytes_local(content: bytes, filename: str, base_path: str):
    _ensure_dir(base_path)
    path = Path(base_path) / filename
    try:
        path.write_bytes(content)
        return str(path)
    except Exception:
        return None


def _cleanup_local_files(base_path: str, retention_days: int):
    if retention_days <= 0:
        return
    try:
        cutoff = datetime.now().timestamp() - retention_days * 86400
        p = Path(base_path)
        if not p.exists():
            return
        for f in p.glob("*"):
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        return


_CLEANUP_THREAD_STARTED = False


def _start_cleanup_daemon():
    global _CLEANUP_THREAD_STARTED
    if _CLEANUP_THREAD_STARTED:
        return
    _CLEANUP_THREAD_STARTED = True

    def loop():
        while True:
            stype, retention, base_path, _ = _get_storage_settings()
            if stype in ("local", "s3"):
                _cleanup_local_files(base_path, retention)
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True).start()


def _s3_client(s):
    import boto3

    endpoint = (os.getenv("S3_ENDPOINT") or s.get("s3_endpoint") or "").strip() or None
    region = (os.getenv("S3_REGION") or s.get("s3_region") or "").strip() or None
    ak = (os.getenv("S3_ACCESS_KEY") or s.get("s3_access_key") or "").strip() or None
    sk = (os.getenv("S3_SECRET_KEY") or s.get("s3_secret_key") or "").strip() or None
    cfg = {}
    if endpoint:
        cfg["endpoint_url"] = endpoint
    if region:
        cfg["region_name"] = region
    if ak and sk:
        cfg["aws_access_key_id"] = ak
        cfg["aws_secret_access_key"] = sk
    return boto3.client("s3", **cfg)


def _upload_to_s3(content: bytes, filename: str, s):
    try:
        bucket = (os.getenv("S3_BUCKET") or s.get("s3_bucket") or "").strip()
        if not bucket:
            return None, "S3_BUCKET 未配置"
        prefix = (os.getenv("S3_PREFIX") or s.get("s3_prefix") or "").strip()
        key = f"{prefix}{filename}" if prefix else filename
        cli = _s3_client(s)
        cli.put_object(
            Bucket=bucket, Key=key, Body=content, ContentType="application/zip"
        )
        expires = int(
            os.getenv("S3_PRESIGN_EXPIRES") or s.get("s3_presign_expires") or 86400
        )
        url = cli.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires
        )
        return url, None
    except Exception as e:
        return None, str(e)


def maybe_persist_and_upload(content: bytes, filename: str):
    stype, retention, base_path, s = _get_storage_settings()
    _start_cleanup_daemon()
    url = None
    err = None
    if stype in ("local", "s3") and retention != 0:
        _save_bytes_local(content, filename, base_path)
    if stype == "s3":
        try:
            url, err = _upload_to_s3(content, filename, s)
        except Exception as e:
            url, err = None, str(e)
    return stype, retention, url, err


def get_user_id():
    if "user_id" not in st.session_state:
        st.session_state.user_id = hashlib.md5(
            f"{datetime.now().timestamp()}{random.random()}".encode()
        ).hexdigest()[:12]
    return st.session_state.user_id


USAGE_STATS_LOCK = threading.RLock()


def get_users():
    return load_json(USERS_FILE, {})


def save_users(data):
    return save_json(USERS_FILE, data)


def get_user(uid):
    with USAGE_STATS_LOCK:
        users = get_users()
        if uid not in users:
            users[uid] = {"daily": {}, "total": 0, "vip": False, "tokens_used": 0}
            save_users(users)
        return users[uid]


def update_user_usage(uid, count=1, tokens=0):
    with USAGE_STATS_LOCK:
        users = get_users()
        user = users.get(uid, {"daily": {}, "total": 0, "tokens_used": 0})
        today = date.today().isoformat()
        user["daily"][today] = user["daily"].get(today, 0) + count
        user["total"] = user.get("total", 0) + count
        user["tokens_used"] = user.get("tokens_used", 0) + tokens
        users[uid] = user
        save_users(users)


def check_user_limit(uid):
    with USAGE_STATS_LOCK:
        s = get_settings()
        user = get_user(uid)
        today = date.today().isoformat()
        used = user["daily"].get(today, 0)
        limit = s["daily_limit_vip"] if user.get("vip") else s["daily_limit_user"]
        return used < limit, used, limit


def get_stats():
    stats = load_json(
        STATS_FILE,
        {
            "daily": {},
            "total": 0,
            "tokens_total": 0,
            "daily_images": {},
            "images_total": 0,
        },
    )
    if "daily" not in stats or not isinstance(stats.get("daily"), dict):
        stats["daily"] = {}
    if "daily_images" not in stats or not isinstance(stats.get("daily_images"), dict):
        stats["daily_images"] = {}
    if "total" not in stats:
        stats["total"] = 0
    if "tokens_total" not in stats:
        stats["tokens_total"] = 0
    if "images_total" not in stats:
        stats["images_total"] = 0
    return stats


def update_stats(count=1, tokens=0, image_count=0):
    with USAGE_STATS_LOCK:
        stats = get_stats()
        today = date.today().isoformat()
        stats["daily"][today] = stats["daily"].get(today, 0) + count
        stats["total"] = stats.get("total", 0) + count
        stats["tokens_total"] = stats.get("tokens_total", 0) + tokens
        image_inc = max(0, int(image_count or 0))
        stats["daily_images"][today] = stats["daily_images"].get(today, 0) + image_inc
        stats["images_total"] = stats.get("images_total", 0) + image_inc
        save_json(STATS_FILE, stats)


def record_platform_usage_event_safe(
    feature: str,
    provider: str,
    model: str,
    request_count: int,
    output_images: int,
    tokens_used: int,
    charge_source: str,
    actor_label: str,
    metadata_json=None,
):
    if not platform_database_enabled():
        return
    try:
        payload = {
            "feature": feature,
            "provider": provider,
            "model": model,
            "request_count": int(request_count or 0),
            "output_images": int(output_images or 0),
            "tokens_used": int(tokens_used or 0),
            "charge_source": charge_source,
            "actor_label": actor_label,
            "metadata": metadata_json or {},
            "clock": time.time_ns(),
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        with session_scope() as session:
            record_usage_event(
                session,
                feature=feature,
                provider=provider,
                model=model,
                request_count=request_count,
                output_images=output_images,
                tokens_used=tokens_used,
                charge_source=charge_source,
                actor_label=actor_label,
                idempotency_key=f"usage:{digest}",
                metadata_json=metadata_json,
            )
    except Exception:
        pass


def count_generated_images(results):
    if not results:
        return 0
    return sum(
        1
        for item in results
        if item.get("translated") is not None or item.get("image") is not None
    )


def get_today_generated_images_count() -> int:
    stats = get_stats()
    return int(stats.get("daily_images", {}).get(date.today().isoformat(), 0) or 0)


# ==================== 合规检测 ====================
def check_compliance(text, mode=None):
    if not text:
        return True, text, ""
    if mode is None:
        mode = st.session_state.get("user_compliance_mode", "strict")
    comp = get_compliance()
    preset = comp["presets"].get(mode, comp["presets"]["strict"])
    blacklist = set(w.lower() for w in preset.get("blacklist", []))
    blacklist.update(w.lower() for w in comp.get("custom_blacklist", []))
    uid = get_user_id()
    user_custom = comp.get("user_custom", {}).get(uid, {})
    blacklist.update(w.lower() for w in user_custom.get("blacklist", []))
    whitelist = set(w.lower() for w in comp.get("whitelist", []))
    whitelist.update(w.lower() for w in user_custom.get("whitelist", []))
    text_lower = text.lower()
    issues = [w for w in blacklist if w in text_lower and w not in whitelist]
    if issues:
        return False, text, f"风险词: {', '.join(issues[:5])}"
    return True, text, ""


def save_user_compliance(uid, blacklist=None, whitelist=None):
    comp = get_compliance()
    if "user_custom" not in comp:
        comp["user_custom"] = {}
    if uid not in comp["user_custom"]:
        comp["user_custom"][uid] = {"blacklist": [], "whitelist": []}
    if blacklist is not None:
        comp["user_custom"][uid]["blacklist"] = blacklist
    if whitelist is not None:
        comp["user_custom"][uid]["whitelist"] = whitelist
    save_compliance(comp)


def get_translate_compliance_templates():
    comp = get_compliance()
    templates = comp.get("translate_templates", {})
    enabled = {k: v for k, v in templates.items() if v.get("enabled", True)}
    return templates, enabled


def parse_compliance_words(text):
    if not text:
        return []
    parts = re.split(r"[,\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def find_compliance_hits(text, terms):
    if not text or not terms:
        return []
    text_lower = text.lower()
    hits = [t for t in terms if t.lower() in text_lower]
    return list(dict.fromkeys(hits))


def format_runtime_error_message(error, max_len=220):
    raw = str(error).strip() if error is not None else ""
    lower = raw.lower()
    if "model_not_found" in lower or "no available channel for model" in lower:
        return "⚠️ 当前中转站该模型没有可用通道，请切换其他模型或稍后再试。"
    if "generation failed" in lower:
        return "⚠️ 中转站图片生成失败，请换一个模型或稍后再试。"
    if "wss connection timeout" in lower or '"limited"' in lower:
        return "⚠️ 中转站上游超时或限流，请降低并发并稍后重试。"
    if "api key invalid" in lower or "invalid api key" in lower:
        return "⚠️ API Key 无效，请检查后重试。"
    if "user location is not supported for the api use" in lower or (
        "failed_precondition" in lower and "location is not supported" in lower
    ):
        return "⚠️ 当前服务器出口IP不在 Gemini API 可用地区（FAILED_PRECONDITION）。请切换到受支持地区节点（如 US/JP/SG），或改用 Vertex AI 区域端点。"
    if (
        "deadline_exceeded" in lower
        or "deadline expired before operation could complete" in lower
        or ("504" in lower and "deadline" in lower)
    ):
        return "⚠️ 请求超时（DEADLINE_EXCEEDED）。当前任务复杂度较高：请减少参考图数量、保持 1K 分辨率，或稍后重试。"
    return raw[:max_len] if max_len and len(raw) > max_len else raw


# ==================== AI 客户端 ====================
class GeminiClient:
    """Gemini Image 客户端（当前锁定 Nano Banana 2）"""

    def __init__(self, api_key, model=PRIMARY_IMAGE_MODEL, timeout_ms: int = 180000):
        self.api_key = api_key
        self.model = PRIMARY_IMAGE_MODEL
        self.timeout_ms = timeout_ms
        self.use_vertex_express = should_use_vertex_express(api_key)
        http_opts = None
        try:
            http_opts = types.HttpOptions(timeout=timeout_ms)
        except Exception:
            http_opts = None
        self.client = create_genai_client(api_key, http_options=http_opts)
        self.prompts = self._load_prompts_safe()
        self.total_tokens = 0
        self.last_error = None

    def _load_prompts_safe(self):
        prompts = get_prompts()
        for key, default_value in DEFAULT_PROMPTS.items():
            if key not in prompts or not prompts[key]:
                prompts[key] = default_value
        return prompts

    def _call(self, func, retries=3):
        def _backoff(attempt_idx: int, base_sec: float = 1.2, max_sec: float = 12.0):
            wait_sec = min(max_sec, (2**attempt_idx) * base_sec) + random.uniform(
                0.2, 0.9
            )
            time.sleep(wait_sec)

        for i in range(retries):
            try:
                with GEMINI_CALL_SEMAPHORE:
                    return func()
            except Exception as e:
                self.last_error = str(e)
                err = str(e).lower()
                if (
                    "api key expired" in err
                    or "api_key_invalid" in err
                    or "invalid api key" in err
                ):
                    raise Exception(
                        "⚠️ API Key 无效或已过期，请更新系统 Key 或自有 Key。"
                    )
                if "user location is not supported for the api use" in err or (
                    "failed_precondition" in err and "location is not supported" in err
                ):
                    if self.use_vertex_express:
                        raise Exception(
                            "⚠️ Vertex AI Express 当前请求被地区/策略限制，请检查 Key 权限或稍后重试。"
                        )
                    raise Exception(
                        "⚠️ 当前服务器出口IP不在 Gemini API 可用地区（FAILED_PRECONDITION）。请切换到受支持地区节点（如 US/JP/SG），或改用 Vertex AI 区域端点。"
                    )
                if (
                    "deadline_exceeded" in err
                    or "deadline expired before operation could complete" in err
                    or ("504" in err and "deadline" in err)
                ):
                    if i < retries - 1:
                        _backoff(i, base_sec=1.8, max_sec=14.0)
                        continue
                    raise Exception(
                        "⚠️ 请求超时（DEADLINE_EXCEEDED）。请减少参考图数量、保持 1K 分辨率，或稍后重试。"
                    )
                if "quota" in err:
                    raise Exception("⚠️ API配额已用尽")
                if (
                    "network" in err
                    or "connection" in err
                    or "timed out" in err
                    or "connection reset" in err
                ):
                    if i < retries - 1:
                        _backoff(i, base_sec=1.0, max_sec=8.0)
                        continue
                    raise Exception("⚠️ 网络连接失败")
                if (
                    "overloaded" in err
                    or "503" in err
                    or "unavailable" in err
                    or "internal" in err
                ):
                    if i < retries - 1:
                        _backoff(i, base_sec=1.5, max_sec=10.0)
                        continue
                    raise Exception("⚠️ 模型繁忙，请稍后重试，或减少参考图/降低分辨率。")
                if "rate" in err or "429" in err or "resource_exhausted" in err:
                    if i < retries - 1:
                        _backoff(i, base_sec=1.3, max_sec=9.0)
                        continue
                    raise Exception("⚠️ 请求过于频繁")
                if i < retries - 1:
                    _backoff(i, base_sec=0.8, max_sec=6.0)
                    continue
                raise e
        raise Exception(f"⚠️ 请求失败: {self.last_error}")

    def _prep_images(self, images, max_count=3):
        parts = []
        for img in images[:max_count]:
            buf = io.BytesIO()
            ic = img.copy()
            if max(ic.size) > 1024:
                ic.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            ic.save(buf, format="PNG", optimize=True)
            parts.append(
                types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")
            )
        return parts

    def _count_tokens(self, response):
        try:
            if hasattr(response, "usage_metadata"):
                tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
                self.total_tokens += tokens
                return tokens
        except:
            pass
        return 0

    def _parse_json_response(self, text, default=None):
        if not text:
            return default if default is not None else {}

        text = text.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass

        try:
            match = re.search(r"\[[^\[\]]*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass

        return default if default is not None else {}

    def get_tokens_used(self):
        return self.total_tokens

    def get_last_error(self):
        return self.last_error

    def _target_is_english(self, target_lang) -> bool:
        normalized = str(target_lang or "").strip().lower()
        if not normalized:
            return False
        if normalized in {"en", "english", "us english", "american english"}:
            return True
        return "english" in normalized

    def _lines_have_cjk(self, lines) -> bool:
        if not lines:
            return False
        return any(contains_cjk(str(line)) for line in lines if str(line).strip())

    def analyze_product(self, images, name="", detail=""):
        default_result = {
            "product_name_en": name or "Product",
            "product_name_zh": name or "商品",
            "primary_category": "General",
            "visual_attrs": ["quality", "design"],
            "confidence": 0.5,
        }

        if not images:
            return default_result

        parts = self._prep_images(images, 5)

        prompt_template = self.prompts.get(
            "anchor_analysis", DEFAULT_PROMPTS["anchor_analysis"]
        )
        try:
            prompt = prompt_template.format(
                product_name=name or "N/A", product_detail=detail or "N/A"
            )
        except KeyError:
            prompt = f"""Analyze these product images and return JSON:
{{"primary_category": "category", "product_name_en": "English name", "product_name_zh": "中文名", "visual_attrs": ["attr1", "attr2"], "confidence": 0.8}}
Product name: {name or "N/A"}
Product detail: {detail or "N/A"}
Return valid JSON only."""

        parts.append(prompt)

        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=PRIMARY_IMAGE_MODEL,
                    contents=parts,
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)

            if resp.text:
                result = self._parse_json_response(resp.text, default_result)
                for key, value in default_result.items():
                    if key not in result or not result[key]:
                        result[key] = value
                return result
            return default_result
        except Exception as e:
            self.last_error = str(e)
            return default_result

    def generate_requirements(self, anchor, types_counts, tags=None):
        templates = get_templates()["combo_types"]
        types_str = ", ".join(
            [f"{templates[k]['name']}x{v}" for k, v in types_counts.items()]
        )

        prompt_template = self.prompts.get(
            "requirements_gen", DEFAULT_PROMPTS["requirements_gen"]
        )
        try:
            prompt = prompt_template.format(
                product_name=anchor.get("product_name_zh", "商品"),
                category=anchor.get("primary_category", "General"),
                features=", ".join(anchor.get("visual_attrs", [])[:3]),
                tags=", ".join(tags) if tags else "无",
                types=types_str,
            )
        except KeyError:
            return []

        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=PRIMARY_IMAGE_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)
            result = self._parse_json_response(resp.text if resp.text else "[]", [])
            return result if isinstance(result, list) else []
        except Exception as e:
            self.last_error = str(e)
            return []

    def generate_en_copy(self, anchor, requirements):
        if not requirements:
            return requirements

        req_str = "\n".join(
            [f"- {r.get('type_name', '')}: {r.get('topic', '')}" for r in requirements]
        )
        prompt_template = self.prompts.get(
            "en_copy_gen", DEFAULT_PROMPTS["en_copy_gen"]
        )

        try:
            prompt = prompt_template.format(
                product_name=anchor.get("product_name_en", "Product"),
                category=anchor.get("primary_category", "General"),
                requirements=req_str,
            )
        except KeyError:
            return requirements

        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=PRIMARY_IMAGE_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)

            copies = self._parse_json_response(resp.text if resp.text else "[]", [])
            if not isinstance(copies, list):
                return requirements

            copy_map = {(c.get("type_key"), c.get("index")): c for c in copies}
            for r in requirements:
                key = (r.get("type_key"), r.get("index"))
                if key in copy_map:
                    c = copy_map[key]
                    r["headline"] = re.sub(
                        r"[^a-zA-Z0-9\s]", "", c.get("headline", "")
                    )[:MAX_HEADLINE_CHARS]
                    r["subline"] = re.sub(r"[^a-zA-Z0-9\s]", "", c.get("subline", ""))[
                        :MAX_SUBLINE_CHARS
                    ]
                    r["badge"] = re.sub(r"[^a-zA-Z0-9\s]", "", c.get("badge", ""))[
                        :MAX_BADGE_CHARS
                    ]
            return requirements
        except Exception as e:
            self.last_error = str(e)
            return requirements

    def compose_image_prompt(self, anchor, req, aspect="1:1"):
        templates = get_templates()["combo_types"]
        type_info = templates.get(req.get("type_key", ""), {})

        if req.get("type_key") == "size":
            prompt_template = self.prompts.get(
                "size_image_prompt", DEFAULT_PROMPTS["size_image_prompt"]
            )
            try:
                return prompt_template.format(
                    product_name=anchor.get("product_name_en", "Product"),
                    aspect_ratio=aspect,
                )
            except KeyError:
                return f"Professional product dimension diagram. Product: {anchor.get('product_name_en', 'Product')}. Aspect: {aspect}"

        text_content = ""
        if req.get("headline"):
            text_content = f"Headline: {req['headline']}"
            if req.get("subline"):
                text_content += f"\nSubline: {req['subline']}"
            if req.get("badge"):
                text_content += f"\nBadge: {req['badge']}"

        prompt_template = self.prompts.get(
            "image_prompt", DEFAULT_PROMPTS["image_prompt"]
        )
        try:
            return prompt_template.format(
                product_name=anchor.get("product_name_en", "Product"),
                category=anchor.get("primary_category", "General"),
                image_type=req.get("type_name", ""),
                style_hint=type_info.get("hint", ""),
                scene=req.get("scene", ""),
                text_content=text_content,
                aspect_ratio=aspect,
            )
        except KeyError:
            return f"Professional ecommerce product image. Product: {anchor.get('product_name_en', 'Product')}. Aspect: {aspect}"

    def generate_image(
        self,
        refs,
        prompt,
        aspect="1:1",
        size="1K",
        thinking_level="minimal",
        enforce_english=False,
        max_attempts=1,
    ):
        """生成图片 - 支持英文文本校验与自动重试"""
        max_refs = MODELS.get(self.model, {}).get("max_refs", 3)

        def _generate_once(extra_guard=""):
            parts = self._prep_images(refs, min(len(refs), max_refs))
            guard = "CRITICAL: ALL text in the image MUST be ENGLISH only. NO Chinese/Japanese/Korean characters."
            if extra_guard:
                guard = f"{guard}\n{extra_guard}"
            full_prompt = f"""{guard}

{prompt}"""
            parts.append(full_prompt)

            model_info = MODELS.get(self.model, MODELS[PRIMARY_IMAGE_MODEL])
            available_res = model_info.get("resolutions", ["1K"])
            target_size = size if size in available_res else "1K"
            image_config = types.ImageConfig(aspect_ratio=aspect)
            if target_size in ["2K", "4K"]:
                image_config = types.ImageConfig(
                    aspect_ratio=aspect, image_size=target_size
                )

            cfg_kwargs = {
                "response_modalities": ["IMAGE"],
                "image_config": image_config,
            }
            if model_info.get("supports_thinking", False):
                thinking_cfg = thinking_config_from_level(thinking_level)
                if thinking_cfg:
                    cfg_kwargs["thinking_config"] = thinking_cfg
            config = types.GenerateContentConfig(**cfg_kwargs)

            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=self.model, contents=parts, config=config
                )
            )
            self._count_tokens(resp)

            if resp.candidates:
                for part in resp.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        img_data = part.inline_data.data
                        if img_data:
                            return Image.open(io.BytesIO(img_data))
            return None

        attempts = max(1, int(max_attempts or 1))
        for i in range(attempts):
            extra_guard = (
                "STRICT: Remove any non-English text. Use English only."
                if i > 0
                else ""
            )
            try:
                img = _generate_once(extra_guard=extra_guard)
            except Exception as e:
                self.last_error = str(e)
                raise e
            if not img:
                self.last_error = "API返回无图片数据"
                if i == attempts - 1:
                    return None
                continue
            if not enforce_english:
                return img
            # OCR 检测是否出现中日韩字符
            ocr = self.extract_text_from_image(img, source_lang="auto")
            text = " ".join(ocr.get("lines", []))
            if contains_cjk(text):
                self.last_error = "检测到非英文文本，自动重试"
                continue
            return img
        return None

    def generate_titles(self, product_info, template_prompt):
        """生成商品标题 - 支持中英双语"""
        prompt = template_prompt.replace("{product_info}", product_info)
        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=PRIMARY_IMAGE_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)
            text = resp.text.strip() if resp.text else ""

            # 解析中英双语标题
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            # 过滤掉标签行
            clean_lines = []
            for line in lines:
                cleaned = re.sub(
                    r"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|English[:]\s*|Chinese[:]\s*|中文[:]\s*)",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if cleaned:
                    clean_lines.append(cleaned)

            return clean_lines[:6] if len(clean_lines) >= 6 else clean_lines
        except Exception as e:
            self.last_error = str(e)
            return []

    def generate_titles_from_image(self, images, product_info="", template_prompt=None):
        """从图片分析生成商品标题"""
        if not images:
            return []

        parts = self._prep_images(images, 5)

        if template_prompt is None:
            template_prompt = DEFAULT_TITLE_TEMPLATES.get("image_analysis", {}).get(
                "prompt", ""
            )

        prompt = template_prompt.replace(
            "{product_info}", product_info or "No additional info provided"
        )
        parts.append(prompt)

        try:
            model_name = self.model or PRIMARY_IMAGE_MODEL
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)
            text = resp.text.strip() if resp.text else ""
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            clean_lines = []
            for line in lines:
                cleaned = re.sub(
                    r"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|English[:]\s*|Chinese[:]\s*|中文[:]\s*)",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if cleaned:
                    clean_lines.append(cleaned)
            return clean_lines[:6] if len(clean_lines) >= 6 else clean_lines
        except Exception as e:
            self.last_error = str(e)
            return []

    def extract_text_from_image(self, image, source_lang="auto"):
        """提取图片中文字"""
        if image is None:
            return {"language": source_lang, "lines": []}
        parts = self._prep_images([image], 1)
        prompt_template = self.prompts.get(
            "image_text_extract", DEFAULT_PROMPTS["image_text_extract"]
        )
        try:
            prompt = prompt_template.format(source_lang=source_lang or "auto")
        except KeyError:
            prompt = f"""Extract all visible text and return JSON only:
{{"language":"auto","lines":["line1","line2"]}}
Source language hint: {source_lang or "auto"}"""
        parts.append(prompt)
        try:
            model_name = self.model or PRIMARY_IMAGE_MODEL
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                )
            )
            self._count_tokens(resp)
            parsed = self._parse_json_response(resp.text if resp.text else "", {})
            if isinstance(parsed, list):
                lines = parsed
                language = source_lang
            elif isinstance(parsed, dict):
                lines = parsed.get("lines") or parsed.get("text") or []
                language = parsed.get("language") or source_lang
            else:
                lines = []
                language = source_lang
            cleaned = [str(l).strip() for l in lines if str(l).strip()]
            return {"language": language or source_lang, "lines": cleaned}
        except Exception as e:
            self.last_error = str(e)
            return {"language": source_lang, "lines": []}

    def translate_lines(
        self,
        lines,
        source_lang="auto",
        target_lang="English",
        style_hint="Literal",
        avoid_terms=None,
        enforce_english=False,
        max_attempts=1,
    ):
        """翻译文本行"""
        if not lines:
            return []
        lines_json = json.dumps(lines, ensure_ascii=False)
        prompt_template = self.prompts.get(
            "image_text_translate", DEFAULT_PROMPTS["image_text_translate"]
        )
        avoid_terms_text = ", ".join(avoid_terms) if avoid_terms else "None"
        try:
            base_prompt = prompt_template.format(
                source_lang=source_lang or "auto",
                target_lang=target_lang,
                style_hint=style_hint,
                lines_json=lines_json,
                avoid_terms=avoid_terms_text,
            )
        except KeyError:
            base_prompt = f"""Translate each line to {target_lang} from {source_lang or "auto"}.
Style: {style_hint}
Avoid these compliance terms in output (if any): {avoid_terms_text}
Return JSON array only.
Lines JSON: {lines_json}"""
        attempts = max(1, int(max_attempts or 1))
        must_enforce_english = bool(enforce_english) or self._target_is_english(
            target_lang
        )
        model_name = self.model or PRIMARY_IMAGE_MODEL
        for i in range(attempts):
            prompt = base_prompt
            if avoid_terms and "avoid" not in prompt.lower():
                prompt = f"{prompt}\nAvoid these compliance terms in output (if any): {avoid_terms_text}"
            if must_enforce_english:
                strict_guard = "CRITICAL: Output must be US English only. Do not output any Chinese/Japanese/Korean characters. Keep line count aligned."
                if i > 0:
                    strict_guard += " This is a retry because non-English characters were detected previously."
                prompt = f"{prompt}\n{strict_guard}"
            try:
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=model_name,
                        contents=[prompt],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT"]
                        ),
                    )
                )
                self._count_tokens(resp)
                parsed = self._parse_json_response(resp.text if resp.text else "", [])
                if isinstance(parsed, dict) and parsed.get("lines"):
                    translated = parsed.get("lines") or []
                elif isinstance(parsed, list):
                    translated = parsed
                else:
                    translated = [
                        l.strip() for l in (resp.text or "").split("\n") if l.strip()
                    ]
                cleaned = [str(l).strip() for l in translated if str(l).strip()]
                if must_enforce_english and self._lines_have_cjk(cleaned):
                    self.last_error = "检测到中文残留，正在自动重试英文重写"
                    if i < attempts - 1:
                        continue
                    return []
                return cleaned
            except Exception as e:
                self.last_error = str(e)
                if i < attempts - 1:
                    continue
                return []
        return []

    def extract_and_translate_image_text(
        self,
        image,
        source_lang="auto",
        target_lang="English",
        style_hint="Literal",
        avoid_terms=None,
        enforce_english=False,
        max_attempts=1,
    ):
        """一次请求完成 OCR + 文本翻译，减少往返延迟"""
        if image is None:
            return {"language": source_lang, "source_lines": [], "translated_lines": []}
        prompt_template = self.prompts.get(
            "image_text_extract_translate",
            DEFAULT_PROMPTS["image_text_extract_translate"],
        )
        avoid_terms_text = ", ".join(avoid_terms) if avoid_terms else "None"
        try:
            base_prompt = prompt_template.format(
                source_lang=source_lang or "auto",
                target_lang=target_lang,
                style_hint=style_hint,
                avoid_terms=avoid_terms_text,
            )
        except KeyError:
            base_prompt = f"""Extract visible text from image then translate to {target_lang}.
Source language hint: {source_lang or "auto"}
Style: {style_hint}
Avoid terms: {avoid_terms_text}
Return JSON only:
{{"language":"auto","source_lines":[],"translated_lines":[]}}"""
        attempts = max(1, int(max_attempts or 1))
        must_enforce_english = bool(enforce_english) or self._target_is_english(
            target_lang
        )
        model_name = self.model or PRIMARY_IMAGE_MODEL
        for i in range(attempts):
            parts = self._prep_images([image], 1)
            prompt = base_prompt
            if must_enforce_english:
                strict_guard = "CRITICAL: translated_lines must be US English only. No Chinese/Japanese/Korean characters."
                if i > 0:
                    strict_guard += " This is a retry because non-English characters were detected previously."
                prompt = f"{prompt}\n{strict_guard}"
            parts.append(prompt)
            try:
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=model_name,
                        contents=parts,
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT"]
                        ),
                    )
                )
                self._count_tokens(resp)
                parsed = self._parse_json_response(resp.text if resp.text else "", {})
                if not isinstance(parsed, dict):
                    if i < attempts - 1:
                        continue
                    return {
                        "language": source_lang,
                        "source_lines": [],
                        "translated_lines": [],
                    }
                src_lines = parsed.get("source_lines") or parsed.get("lines") or []
                tgt_lines = parsed.get("translated_lines") or []
                src_clean = [
                    str(line).strip() for line in src_lines if str(line).strip()
                ]
                tgt_clean = [
                    str(line).strip() for line in tgt_lines if str(line).strip()
                ]
                if src_clean and tgt_clean and len(tgt_clean) < len(src_clean):
                    tgt_clean = tgt_clean + src_clean[len(tgt_clean) :]
                if must_enforce_english and self._lines_have_cjk(tgt_clean):
                    self.last_error = "检测到中文残留，正在自动重试英文重写"
                    if i < attempts - 1:
                        continue
                    return {
                        "language": parsed.get("language") or source_lang,
                        "source_lines": src_clean,
                        "translated_lines": [],
                    }
                return {
                    "language": parsed.get("language") or source_lang,
                    "source_lines": src_clean,
                    "translated_lines": tgt_clean,
                }
            except Exception as e:
                self.last_error = str(e)
                if i < attempts - 1:
                    continue
                return {
                    "language": source_lang,
                    "source_lines": [],
                    "translated_lines": [],
                }
        return {"language": source_lang, "source_lines": [], "translated_lines": []}

    def translate_image(
        self,
        image,
        target_lang="English",
        source_lang="auto",
        style_hint="Literal",
        layout_hint="Preserve layout",
        aspect="1:1",
        size="1K",
        thinking_level="minimal",
        avoid_terms=None,
        enforce_english=False,
        max_attempts=1,
        cleanup_cn_overlay=True,
    ):
        """翻译图片内文字并生成新图"""
        if image is None:
            return None
        prompt_template = self.prompts.get(
            "image_translate_prompt", DEFAULT_PROMPTS["image_translate_prompt"]
        )
        avoid_terms_text = ", ".join(avoid_terms) if avoid_terms else "None"
        try:
            base_prompt = prompt_template.format(
                source_lang=source_lang or "auto",
                target_lang=target_lang,
                style_hint=style_hint,
                layout_hint=layout_hint,
                avoid_terms=avoid_terms_text,
            )
        except KeyError:
            base_prompt = f"""Translate all visible text from {source_lang or "auto"} to {target_lang}.
Style: {style_hint}
Layout: {layout_hint}
Avoid these compliance terms in output (if any): {avoid_terms_text}
Output image only."""
        if avoid_terms and "avoid" not in base_prompt.lower():
            base_prompt = f"{base_prompt}\nAvoid these compliance terms in output (if any): {avoid_terms_text}"
        if cleanup_cn_overlay:
            base_prompt = (
                f"{base_prompt}\n"
                "Cleanup policy: Remove non-product Chinese overlay text corner labels and stamp-style Chinese marks when they are decorative overlays. "
                "For removed overlays, rebuild natural clean background with consistent texture. "
                "Do not remove brand logos trademark logos certification logos or required product labels."
            )

        model_info = MODELS.get(self.model, MODELS[PRIMARY_IMAGE_MODEL])
        available_res = model_info.get("resolutions", ["1K"])
        target_size = size if size in available_res else "1K"
        image_config = types.ImageConfig(aspect_ratio=aspect)
        if target_size in ["2K", "4K"]:
            image_config = types.ImageConfig(
                aspect_ratio=aspect, image_size=target_size
            )

        cfg_kwargs = {"response_modalities": ["IMAGE"], "image_config": image_config}
        if model_info.get("supports_thinking", False):
            thinking_cfg = thinking_config_from_level(thinking_level)
            if thinking_cfg:
                cfg_kwargs["thinking_config"] = thinking_cfg
        config = types.GenerateContentConfig(**cfg_kwargs)
        attempts = max(1, int(max_attempts or 1))
        must_enforce_english = bool(enforce_english) or self._target_is_english(
            target_lang
        )
        for i in range(attempts):
            extra_guard = ""
            if must_enforce_english:
                extra_guard = "CRITICAL: ALL rendered text in output image must be US English only. No Chinese/Japanese/Korean characters."
                if i > 0:
                    extra_guard += " This is a retry because non-English characters were detected previously."
            prompt = f"{base_prompt}\n{extra_guard}" if extra_guard else base_prompt
            parts = self._prep_images([image], 1)
            parts.append(prompt)
            try:
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=self.model, contents=parts, config=config
                    )
                )
                self._count_tokens(resp)
                translated_img = None
                if resp.candidates:
                    for part in resp.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            img_data = part.inline_data.data
                            if img_data:
                                translated_img = Image.open(io.BytesIO(img_data))
                                break
                if translated_img is None:
                    self.last_error = "API返回无图片数据"
                    if i < attempts - 1:
                        continue
                    return None
                if must_enforce_english:
                    ocr = self.extract_text_from_image(
                        translated_img, source_lang="auto"
                    )
                    text = " ".join(ocr.get("lines", []))
                    if contains_cjk(text):
                        self.last_error = "检测到非英文文本，正在自动重试出图"
                        if i < attempts - 1:
                            continue
                        return None
                return translated_img
            except Exception as e:
                self.last_error = str(e)
                if i < attempts - 1:
                    continue
                raise e
        return None


# ==================== 中转站图片客户端 ====================
class RelayImageClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = RELAY_API_BASE,
        timeout_sec: int = 180,
    ):
        self.api_key = str(api_key or "").strip()
        self.model = model
        self.base_url = str(base_url or RELAY_API_BASE).rstrip("/")
        self.timeout_sec = timeout_sec
        self.last_error = None
        self.total_tokens = 0

    def get_last_error(self):
        return self.last_error

    def get_tokens_used(self):
        return self.total_tokens

    def _build_messages(self, refs, prompt: str):
        content = [{"type": "text", "text": prompt}]
        for ref in (refs or [])[:3]:
            try:
                img = resize_max_side(ref.copy(), 1024)
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode()
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            except Exception:
                continue
        return [{"role": "user", "content": content}]

    def _extract_image_from_response(self, payload: dict):
        if not isinstance(payload, dict):
            return None
        for item in payload.get("data", []) or []:
            if item.get("b64_json"):
                return Image.open(io.BytesIO(base64.b64decode(item["b64_json"])))
            if item.get("url"):
                response = requests.get(item["url"], timeout=60)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content))
        choices = payload.get("choices", []) or []
        for choice in choices:
            message = choice.get("message", {}) or {}
            content = message.get("content")
            if isinstance(content, str):
                match = re.search(r"(https?://\\S+)", content)
                if match:
                    response = requests.get(match.group(1), timeout=60)
                    response.raise_for_status()
                    return Image.open(io.BytesIO(response.content))
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    image_url = part.get("image_url")
                    if isinstance(image_url, dict) and image_url.get("url"):
                        url = image_url["url"]
                        if url.startswith("data:image/") and "," in url:
                            _, b64 = url.split(",", 1)
                            return Image.open(io.BytesIO(base64.b64decode(b64)))
                        response = requests.get(url, timeout=60)
                        response.raise_for_status()
                        return Image.open(io.BytesIO(response.content))
                    if part.get("b64_json"):
                        return Image.open(
                            io.BytesIO(base64.b64decode(part["b64_json"]))
                        )
        return None


def probe_relay_api(base_url: str, api_key: str, model: str = ""):
    base_url = str(base_url or RELAY_API_BASE).rstrip("/")
    api_key = str(api_key or "").strip()
    if not base_url or not api_key:
        return False, "请先填写中转站 API 地址和 API Key。"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(f"{base_url}/models", headers=headers, timeout=20)
        if response.status_code >= 400:
            return False, format_runtime_error_message(response.text)
        payload = response.json()
        model_ids = {
            item.get("id") for item in payload.get("data", []) if isinstance(item, dict)
        }
        if model and model not in model_ids:
            return False, f"模型 `{model}` 不在该中转站的模型列表中。"
        if model:
            return True, f"中转站连接正常，已找到模型 `{model}`。"
        return True, "中转站连接正常。"
    except Exception as e:
        return False, format_runtime_error_message(e)

    def generate_image(
        self,
        refs,
        prompt,
        aspect="1:1",
        size="1K",
        thinking_level="minimal",
        enforce_english=False,
        max_attempts=1,
    ):
        attempts = max(1, int(max_attempts or 1))
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        final_prompt = (
            f"{prompt}\n"
            f"Output requirement: generate one ecommerce image in aspect ratio {aspect}. "
            f"Use English only. Keep product style consistent with references if references are provided."
        )
        for _ in range(attempts):
            try:
                payload = {
                    "model": self.model,
                    "messages": self._build_messages(refs, final_prompt),
                    "temperature": 0.2,
                    "max_tokens": 400,
                }
                response = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout_sec
                )
                text = response.text
                if response.status_code >= 400:
                    self.last_error = text
                    continue
                data = response.json()
                usage = data.get("usage", {}) or {}
                self.total_tokens += int(usage.get("total_tokens") or 0)
                image = self._extract_image_from_response(data)
                if image is not None:
                    return image
                self.last_error = text[:300]
            except Exception as e:
                self.last_error = str(e)
        return None


# ==================== 图片转Base64工具 ====================
def image_to_base64(img: Image.Image) -> str:
    """将PIL Image转换为base64字符串"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64

    return base64.b64encode(buf.getvalue()).decode()


def closest_aspect_ratio(size):
    """根据图片尺寸匹配最接近的宽高比"""
    try:
        w, h = size
        if not w or not h:
            return "1:1"
        ratio = w / h

        def parse_ratio(r):
            a, b = r.split(":")
            return float(a) / float(b)

        return min(ASPECT_RATIOS, key=lambda r: abs(ratio - parse_ratio(r)))
    except Exception:
        return "1:1"


def parse_allowed_formats(val):
    if isinstance(val, list):
        return [str(x).strip().lower() for x in val if str(x).strip()]
    if not val:
        return []
    return [
        x.strip().lower() for x in str(val).replace(";", ",").split(",") if x.strip()
    ]


def sanitize_filename(name, max_len=40):
    base = re.sub(r"[^a-zA-Z0-9_\-]+", "_", name).strip("_")
    if not base:
        base = "image"
    return base[:max_len]


def _ratio_to_float(ratio_str):
    try:
        a, b = ratio_str.split(":")
        return float(a) / float(b)
    except Exception:
        return 1.0


def _average_color(img: Image.Image):
    try:
        thumb = img.copy()
        thumb.thumbnail((64, 64))
        return tuple([int(x) for x in thumb.resize((1, 1)).getpixel((0, 0))])
    except Exception:
        return (255, 255, 255)


def apply_ratio_strategy(
    img: Image.Image, target_ratio: str, method: str = "补边(白色)"
):
    """按目标比例裁切/补边"""
    if not img or not target_ratio:
        return img
    w, h = img.size
    if not w or not h:
        return img
    target = _ratio_to_float(target_ratio)
    current = w / h
    if abs(current - target) < 1e-3:
        return img
    if method.startswith("居中裁切"):
        if current > target:
            new_w = int(h * target)
            left = (w - new_w) // 2
            return img.crop((left, 0, left + new_w, h))
        new_h = int(w / target)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))
    # 补边
    bg = (255, 255, 255) if "白色" in method else _average_color(img)
    if current > target:
        new_h = int(w / target)
        new_img = Image.new("RGB", (w, new_h), bg)
        top = (new_h - h) // 2
        new_img.paste(img, (0, top))
        return new_img
    new_w = int(h * target)
    new_img = Image.new("RGB", (new_w, h), bg)
    left = (new_w - w) // 2
    new_img.paste(img, (left, 0))
    return new_img


def thinking_config_from_level(level):
    """兼容新版SDK的thinking_config：用budget近似表示深度"""
    if not level:
        return None
    lv = str(level).lower()
    if lv in ("minimal", "low"):
        budget = 0  # 关闭/最低思考
    elif lv in ("medium", "high"):
        budget = -1  # 自动
    else:
        return None
    try:
        return types.ThinkingConfig(thinking_budget=budget)
    except Exception:
        return None


def resize_max_side(img: Image.Image, max_side: int):
    if not img or not max_side:
        return img
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def image_to_bytes(
    img: Image.Image, fmt: str = "PNG", quality: int = 85, max_side: int = 0
):
    if img is None:
        return b""
    if max_side and max_side > 0:
        img = resize_max_side(img, max_side)
    buf = io.BytesIO()
    if fmt.upper() in ("JPG", "JPEG"):
        img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=int(quality), optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def get_translated_png_bytes(item: dict) -> bytes:
    data = item.get("translated_png_bytes")
    if data:
        return data
    translated = item.get("translated")
    if translated is None:
        return b""
    data = image_to_bytes(translated, fmt="PNG")
    item["translated_png_bytes"] = data
    return data


def create_translate_zip(results: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in results:
            translated = item.get("translated")
            if translated is None:
                continue
            idx = item.get("index", 0)
            base = item.get("base_name", f"image_{idx:02d}")
            ratio = item.get("ratio_label", "orig")
            size_lbl = item.get("size_label", "1K")
            filename = item.get(
                "filename", f"{idx:02d}_{base}_translated_{ratio}_{size_lbl}.png"
            )
            if not filename.lower().endswith(".png"):
                filename = f"{Path(filename).stem}.png"
            z.writestr(filename, get_translated_png_bytes(item))
    return buf.getvalue()


def format_translate_status(current: int, total: int, mode_text: str = "处理中") -> str:
    current = max(0, int(current))
    total = max(1, int(total))
    ratio = min(100, int((current / total) * 100))
    return f"⏳ {mode_text}: {current}/{total} ({ratio}%)"


def clear_translate_runtime_cache(results: list):
    for item in results:
        if isinstance(item, dict):
            item.pop("original", None)


def get_translate_style_hint(style_choice: str):
    if style_choice == "北美电商英文（偏营销）":
        return "North American ecommerce listing English (Amazon-compliant, TEMU style), persuasive but professional, no slang or colloquial expressions, consistent terminology, US punctuation and units, avoid unsupported absolute claims"
    return "North American ecommerce listing English (Amazon-compliant, TEMU style), formal and professional, no slang or colloquial expressions, consistent terminology, US punctuation and units, avoid unsupported absolute claims"


def execute_image_translate_workload(
    api_key: str, upload_items: list, opts: dict, progress_cb=None, log_cb=None
):
    upload_items = upload_items or []
    total = len(upload_items)
    if total <= 0:
        return [], [], 0

    need_text = bool(opts.get("need_text", True))
    need_image = bool(opts.get("need_image", True))
    fast_text_mode = bool(opts.get("fast_text_mode", True))
    text_workers = max(1, min(6, int(opts.get("text_workers", 2) or 2)))
    source_lang = opts.get("source_lang", "auto")
    target_lang = opts.get("target_lang", "en")
    style_choice = opts.get("style_choice", "北美电商英文（标准）")
    keep_layout = bool(opts.get("keep_layout", True))
    avoid_terms = opts.get("avoid_terms", []) or []
    enable_comp = bool(opts.get("enable_comp", True))
    size_strategy = opts.get("size_strategy", "保留原比例")
    ratio_method = opts.get("ratio_method", "补边(白色)")
    target_ratio = opts.get("target_ratio", "1:1")
    force_1k = bool(opts.get("force_1k", False))
    size = opts.get("size", "1K")
    thinking_level = opts.get("thinking_level", "minimal")
    enforce_english_output = (
        bool(opts.get("force_english_output", False)) and target_lang == "en"
    )
    english_retry_max = max(1, min(5, int(opts.get("english_retry_max", 2) or 2)))
    cleanup_cn_overlay = bool(opts.get("cleanup_cn_overlay", True))
    model_key = opts.get("model_key") or PRIMARY_IMAGE_MODEL
    text_model_key = opts.get("text_model_key") or PRIMARY_IMAGE_MODEL
    batch_size = int(opts.get("batch_size", total) or total)
    batch_size = total if batch_size <= 0 else batch_size

    source_prompt = LANGUAGE_PROMPT_NAMES.get(source_lang, "auto")
    target_prompt = LANGUAGE_PROMPT_NAMES.get(target_lang, "English")
    style_hint = get_translate_style_hint(style_choice)
    layout_hint = (
        "Strictly preserve layout typography and colors"
        if keep_layout
        else "Minor layout adjustments allowed to improve readability"
    )

    mode_label = (
        "text"
        if (need_text and not need_image)
        else ("image" if need_image and not need_text else "text_image")
    )
    ratio_label = (
        "orig" if size_strategy == "保留原比例" else target_ratio.replace(":", "x")
    )
    size_label = size
    if need_image and size_strategy == "强制1:1" and force_1k:
        size_label = "1K"

    image_client = GeminiClient(api_key, model_key)
    text_client = GeminiClient(api_key, text_model_key)
    results = []
    errors = []

    def push_progress(current: int, phase: str):
        if callable(progress_cb):
            progress_cb(current, total, phase)

    def push_log(message: str):
        if callable(log_cb):
            log_cb(message)

    def process_text_single(entry: dict, image_obj: Image.Image):
        if fast_text_mode:
            merged = text_client.extract_and_translate_image_text(
                image_obj,
                source_lang=source_prompt,
                target_lang=target_prompt,
                style_hint=style_hint,
                avoid_terms=avoid_terms,
                enforce_english=enforce_english_output,
                max_attempts=english_retry_max,
            )
            entry["extracted_lines"] = merged.get("source_lines", [])
            entry["translated_lines"] = merged.get("translated_lines", [])
        else:
            extracted = text_client.extract_text_from_image(image_obj, source_prompt)
            entry["extracted_lines"] = extracted.get("lines", [])
            entry["translated_lines"] = text_client.translate_lines(
                entry["extracted_lines"],
                source_lang=source_prompt,
                target_lang=target_prompt,
                style_hint=style_hint,
                avoid_terms=avoid_terms,
                enforce_english=enforce_english_output,
                max_attempts=english_retry_max,
            )
        if (
            enforce_english_output
            and entry["extracted_lines"]
            and not entry["translated_lines"]
        ):
            raise Exception(
                text_client.get_last_error() or "英文校验未通过，请重试或提高重试次数"
            )
        if enable_comp and entry["translated_lines"]:
            hits = []
            for line in entry["translated_lines"]:
                hits.extend(find_compliance_hits(line, avoid_terms))
            entry["compliance_hits"] = list(dict.fromkeys(hits))
        return entry

    if need_text and not need_image and total > 1:
        push_progress(0, "文本翻译中")
        max_workers = min(max(1, text_workers), total)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, item in enumerate(upload_items, start=1):
                img = item["image"]
                base_name = sanitize_filename(item.get("name") or f"image_{i:02d}")
                entry = {
                    "index": i,
                    "translated": None,
                    "extracted_lines": [],
                    "translated_lines": [],
                    "filename": f"{i:02d}_{base_name}_{mode_label}_{ratio_label}_{size_label}.png",
                    "ratio_label": ratio_label,
                    "size_label": size_label,
                    "base_name": base_name,
                    "compliance_hits": [],
                }
                futures[executor.submit(process_text_single, entry, img)] = i

            ordered_map = {}
            done_count = 0
            for fut in as_completed(futures):
                seq = futures[fut]
                try:
                    ordered_map[seq] = fut.result()
                except Exception as e:
                    msg = format_runtime_error_message(e, 220)
                    errors.append(f"图{seq}: {msg}")
                    ordered_map[seq] = {
                        "index": seq,
                        "translated": None,
                        "extracted_lines": [],
                        "translated_lines": [],
                        "filename": f"{seq:02d}_image_{seq:02d}_{mode_label}_{ratio_label}_{size_label}.png",
                        "ratio_label": ratio_label,
                        "size_label": size_label,
                        "base_name": f"image_{seq:02d}",
                        "compliance_hits": [],
                    }
                done_count += 1
                push_progress(done_count, "文本翻译中")
                if done_count % 4 == 0 or done_count == total:
                    push_log(f"已完成文本翻译 {done_count}/{total}")

            for idx in sorted(ordered_map.keys()):
                results.append(ordered_map[idx])
    else:
        for batch_idx, start in enumerate(range(0, total, batch_size), start=1):
            end = min(start + batch_size, total)
            if total > batch_size:
                push_log(
                    f"批次 {batch_idx}/{(total + batch_size - 1) // batch_size}: 图 {start + 1}-{end}"
                )
            for i, item in enumerate(upload_items[start:end], start=start + 1):
                img = item["image"]
                base_name = sanitize_filename(item.get("name") or f"image_{i:02d}")
                entry = {
                    "index": i,
                    "translated": None,
                    "extracted_lines": [],
                    "translated_lines": [],
                    "filename": f"{i:02d}_{base_name}_{mode_label}_{ratio_label}_{size_label}.png",
                    "ratio_label": ratio_label,
                    "size_label": size_label,
                    "base_name": base_name,
                    "compliance_hits": [],
                }
                try:
                    if need_text:
                        entry = process_text_single(entry, img)
                    if need_image:
                        if i % 3 == 1 or i == total:
                            push_log(f"图像翻译生成中：{i}/{total}")
                        aspect = (
                            closest_aspect_ratio(img.size)
                            if size_strategy == "保留原比例"
                            else target_ratio
                        )
                        prepared_img = img
                        if size_strategy != "保留原比例":
                            prepared_img = apply_ratio_strategy(
                                img, target_ratio, ratio_method
                            )
                        model_size = (
                            "1K" if (size_strategy == "强制1:1" and force_1k) else size
                        )
                        entry["translated"] = image_client.translate_image(
                            prepared_img,
                            target_lang=target_prompt,
                            source_lang=source_prompt,
                            style_hint=style_hint,
                            layout_hint=layout_hint,
                            aspect=aspect,
                            size=model_size,
                            thinking_level=thinking_level,
                            avoid_terms=avoid_terms,
                            enforce_english=enforce_english_output,
                            max_attempts=english_retry_max,
                            cleanup_cn_overlay=cleanup_cn_overlay,
                        )
                        if entry["translated"]:
                            if size_strategy != "保留原比例":
                                entry["translated"] = apply_ratio_strategy(
                                    entry["translated"], target_ratio, ratio_method
                                )
                            if size_strategy == "强制1:1" and force_1k:
                                entry["translated"] = entry["translated"].resize(
                                    (1024, 1024), Image.Resampling.LANCZOS
                                )
                        else:
                            raise Exception(
                                image_client.get_last_error() or "返回空图片"
                            )
                except Exception as e:
                    msg = format_runtime_error_message(e, 220)
                    errors.append(f"图{i}: {msg}")
                results.append(entry)
                push_progress(i, "处理中")

    clear_translate_runtime_cache(results)
    tokens_used = image_client.get_tokens_used() + text_client.get_tokens_used()
    return results, errors, tokens_used


try:
    _BG_EXECUTOR_WORKERS = int(
        os.getenv(
            "IMG_TRANSLATE_BG_WORKERS",
            str(DEFAULT_SETTINGS.get("translate_bg_max_concurrent", 2)),
        )
    )
except Exception:
    _BG_EXECUTOR_WORKERS = int(DEFAULT_SETTINGS.get("translate_bg_max_concurrent", 2))
_BG_EXECUTOR_WORKERS = max(1, min(6, _BG_EXECUTOR_WORKERS))
IMAGE_TRANSLATE_BG_EXECUTOR = ThreadPoolExecutor(max_workers=_BG_EXECUTOR_WORKERS)
IMAGE_TRANSLATE_BG_EXECUTOR_WORKERS = _BG_EXECUTOR_WORKERS
IMAGE_TRANSLATE_BG_TASKS = {}
IMAGE_TRANSLATE_BG_LOCK = threading.RLock()
MAX_BG_TASKS = 60


def _bg_now():
    return datetime.now().isoformat(timespec="seconds")


def _prune_bg_tasks_locked():
    if len(IMAGE_TRANSLATE_BG_TASKS) <= MAX_BG_TASKS:
        return
    removable = sorted(
        [
            t
            for t in IMAGE_TRANSLATE_BG_TASKS.values()
            if t.get("status") in ("completed", "failed", "cancelled")
        ],
        key=lambda x: x.get("created_at", ""),
    )
    drop_count = max(0, len(IMAGE_TRANSLATE_BG_TASKS) - MAX_BG_TASKS)
    for item in removable[:drop_count]:
        IMAGE_TRANSLATE_BG_TASKS.pop(item["id"], None)


def _update_bg_task(task_id: str, **kwargs):
    with IMAGE_TRANSLATE_BG_LOCK:
        task = IMAGE_TRANSLATE_BG_TASKS.get(task_id)
        if not task:
            return
        task.update(kwargs)
        task["updated_at"] = _bg_now()


def _ensure_image_translate_bg_executor(workers: int):
    global IMAGE_TRANSLATE_BG_EXECUTOR, IMAGE_TRANSLATE_BG_EXECUTOR_WORKERS
    workers = max(1, min(6, int(workers or 1)))
    with IMAGE_TRANSLATE_BG_LOCK:
        if (
            IMAGE_TRANSLATE_BG_EXECUTOR
            and IMAGE_TRANSLATE_BG_EXECUTOR_WORKERS == workers
        ):
            return IMAGE_TRANSLATE_BG_EXECUTOR
        old_executor = IMAGE_TRANSLATE_BG_EXECUTOR
        IMAGE_TRANSLATE_BG_EXECUTOR = ThreadPoolExecutor(max_workers=workers)
        IMAGE_TRANSLATE_BG_EXECUTOR_WORKERS = workers
    if old_executor:
        try:
            old_executor.shutdown(wait=False)
        except Exception:
            pass
    return IMAGE_TRANSLATE_BG_EXECUTOR


def _run_image_translate_bg_task(task_id: str, payload: dict):
    _update_bg_task(task_id, status="running", message="处理中")
    try:
        total = len(payload.get("upload_items") or [])
        _update_bg_task(task_id, done=0, total=total)

        def progress(done, task_total, phase):
            msg = format_translate_status(done, task_total, phase)
            _update_bg_task(task_id, done=done, total=task_total, message=msg)

        def log(msg):
            _update_bg_task(task_id, message=msg)

        results, errors, tokens_used = execute_image_translate_workload(
            payload.get("api_key"),
            payload.get("upload_items", []),
            payload.get("options", {}),
            progress_cb=progress,
            log_cb=log,
        )

        if payload.get("charge_usage") and payload.get("owner_id"):
            update_user_usage(payload.get("owner_id"), len(results), tokens_used)
            update_stats(
                len(results), tokens_used, image_count=count_generated_images(results)
            )

        record_platform_usage_event_safe(
            feature="image_translate",
            provider="Gemini",
            model=str(
                (payload.get("options") or {}).get("model_key") or PRIMARY_IMAGE_MODEL
            ),
            request_count=total,
            output_images=count_generated_images(results),
            tokens_used=tokens_used,
            charge_source="system_pool" if payload.get("charge_usage") else "own_key",
            actor_label=str(payload.get("owner_id") or "background-job"),
            metadata_json={"mode": "background", "errors": len(errors)},
        )

        _update_bg_task(
            task_id,
            status="completed",
            done=total,
            total=total,
            message=f"✅ 完成 {max(0, len(results) - len(errors))}/{len(results)}",
            result={
                "results": results,
                "errors": errors,
                "tokens_used": tokens_used,
                "source_items": payload.get("upload_items", []),
                "last_options": payload.get("last_options", {}),
            },
            error="",
        )
    except Exception as e:
        _update_bg_task(
            task_id,
            status="failed",
            message="❌ 任务失败",
            error=format_runtime_error_message(e, 220),
        )


def list_image_translate_bg_tasks(owner_id: str):
    with IMAGE_TRANSLATE_BG_LOCK:
        tasks = [
            {k: v for k, v in item.items() if k != "future"}
            for item in IMAGE_TRANSLATE_BG_TASKS.values()
            if item.get("owner_id") == owner_id
            and item.get("task_type") == "image_translate"
        ]
    return sorted(tasks, key=lambda x: x.get("created_at", ""), reverse=True)


def get_image_translate_bg_task(owner_id: str, task_id: str):
    with IMAGE_TRANSLATE_BG_LOCK:
        task = IMAGE_TRANSLATE_BG_TASKS.get(task_id)
        if (
            not task
            or task.get("owner_id") != owner_id
            or task.get("task_type") != "image_translate"
        ):
            return None
        return task


def remove_image_translate_bg_task(owner_id: str, task_id: str):
    with IMAGE_TRANSLATE_BG_LOCK:
        task = IMAGE_TRANSLATE_BG_TASKS.get(task_id)
        if (
            not task
            or task.get("owner_id") != owner_id
            or task.get("task_type") != "image_translate"
        ):
            return False
        if task.get("status") in ("queued", "running"):
            return False
        IMAGE_TRANSLATE_BG_TASKS.pop(task_id, None)
        return True


def submit_image_translate_bg_task(
    owner_id: str, payload: dict, max_concurrent: int = 2
):
    max_concurrent = max(1, min(6, int(max_concurrent or 2)))
    with IMAGE_TRANSLATE_BG_LOCK:
        active_count = sum(
            1
            for t in IMAGE_TRANSLATE_BG_TASKS.values()
            if t.get("owner_id") == owner_id
            and t.get("task_type") == "image_translate"
            and t.get("status") in ("queued", "running")
        )
        if active_count >= max_concurrent:
            raise ValueError(
                f"后台并发上限为 {max_concurrent}，请等待已有任务完成后再提交。"
            )
        executor = _ensure_image_translate_bg_executor(max_concurrent)
        task_id = hashlib.md5(
            f"{time.time()}_{random.random()}_{owner_id}".encode()
        ).hexdigest()[:12]
        task = {
            "id": task_id,
            "task_type": "image_translate",
            "owner_id": owner_id,
            "status": "queued",
            "message": "等待执行",
            "done": 0,
            "total": len(payload.get("upload_items") or []),
            "result": None,
            "error": "",
            "created_at": _bg_now(),
            "updated_at": _bg_now(),
        }
        IMAGE_TRANSLATE_BG_TASKS[task_id] = task
        _prune_bg_tasks_locked()
        fut = executor.submit(_run_image_translate_bg_task, task_id, payload)
        task["future"] = fut
    return task_id


def normalize_requirements(reqs, types_counts, templates):
    """确保图需数量与用户选择一致，避免只生成8张"""
    if not types_counts:
        return reqs
    result = []
    for tk, cnt in types_counts.items():
        if not cnt or cnt <= 0:
            continue
        items = [r for r in reqs if r.get("type_key") == tk]
        if not items:
            info = templates.get(tk, {})
            for i in range(cnt):
                result.append(
                    {
                        "type_key": tk,
                        "type_name": info.get("name", tk),
                        "index": i + 1,
                        "topic": "",
                        "scene": "",
                        "copy": "",
                    }
                )
        else:
            for i in range(cnt):
                base = items[i % len(items)]
                new_item = {**base}
                new_item["type_key"] = tk
                new_item["type_name"] = base.get("type_name") or templates.get(
                    tk, {}
                ).get("name", tk)
                new_item["index"] = i + 1
                result.append(new_item)
    return result


def recommended_ref_limit(model_key: str) -> int:
    return 5


def contains_cjk(text: str) -> bool:
    if not text:
        return False
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
            or 0x3400 <= code <= 0x4DBF  # CJK Extension A
            or 0x3040 <= code <= 0x30FF  # Hiragana/Katakana
            or 0xAC00 <= code <= 0xD7AF  # Hangul
        ):
            return True
    return False


def create_zip_from_results(results: list, titles: list = None) -> bytes:
    """从结果创建ZIP文件"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in results:
            filename = item.get("filename", "image.png")
            img = item.get("image")
            if img:
                img_buf = io.BytesIO()
                img.save(img_buf, format="PNG")
                z.writestr(filename, img_buf.getvalue())

        if titles:
            titles_content = "\n\n".join(
                [
                    f"标题 {i // 2 + 1}:\nEN: {titles[i]}\nCN: {titles[i + 1]}"
                    for i in range(0, len(titles) - 1, 2)
                ]
            )
            if not titles_content and titles:
                titles_content = "\n".join(
                    [f"Title {i + 1}: {t}" for i, t in enumerate(titles)]
                )
            z.writestr("titles.txt", titles_content)

    return buf.getvalue()


# ==================== 样式 ====================
def apply_style():
    st.markdown(
        """<style>
    :root { --primary: #1677ff; --success: #10b981; --warning: #faad14; --danger: #ff4d4f; }
    html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Inter", "SF Pro Text", "Helvetica Neue", Arial, sans-serif; }
    .block-container { padding-top: 0.75rem; padding-bottom: 1.25rem; }
    .main-title { font-size: 2.5rem; font-weight: 800; text-align: center; margin: 1rem 0; background: linear-gradient(135deg, #1677ff 0%, #36cfc9 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .page-title { font-size: 1.75rem; font-weight: 700; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--primary); }
    .stButton>button { border-radius: 10px; font-weight: 600; transition: all 0.2s; border: 1px solid #e2e8f0; background: #f8fafc; color: #0f172a; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12); }
    button[kind="primary"] { background: linear-gradient(135deg, #1677ff 0%, #36cfc9 100%); color: #fff !important; border: 0 !important; box-shadow: 0 6px 16px rgba(22, 119, 255, 0.28); }
    button[kind="primary"]:hover { box-shadow: 0 8px 20px rgba(22, 119, 255, 0.24); }
    button[kind="secondary"] { background: #f1f5f9 !important; color: #0f172a !important; border: 1px solid #e2e8f0 !important; }
    .stButton>button:focus { box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25); }
    [data-testid="stFileUploader"] { border: 2px dashed var(--primary); border-radius: 12px; padding: 1rem; }
    .info-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; }
    .success-card { background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border: 1px solid #86efac; border-radius: 12px; padding: 1rem 1.25rem; }
    .error-card { background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 1px solid #fca5a5; border-radius: 12px; padding: 1rem 1.25rem; }
    .help-section { background: linear-gradient(135deg, #f0f4ff 0%, #faf5ff 100%); border-radius: 14px; padding: 1.25rem; margin: 1rem 0; }
    .title-result { background: #f8fafc; border-left: 4px solid var(--primary); padding: 0.875rem 1.25rem; margin: 0.5rem 0; border-radius: 0 10px 10px 0; }
    .title-bilingual { background: linear-gradient(135deg, #eff6ff 0%, #fef3c7 100%); border: 1px solid #93c5fd; border-radius: 12px; padding: 1rem; margin: 0.75rem 0; }
    .feature-card { background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.25rem; text-align: center; }
    .feature-icon { font-size: 2rem; margin-bottom: 0.5rem; display: block; }
    .feature-title { font-weight: 600; font-size: 15px; margin-bottom: 0.25rem; }
    .feature-desc { font-size: 12px; color: #64748b; }
    .token-badge { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border: 1px solid #f59e0b; border-radius: 8px; padding: 0.25rem 0.75rem; font-size: 12px; font-weight: 500; color: #92400e; display: inline-block; }
    .footer { margin-top: 3rem; padding: 1.5rem; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 12px; }
    #MainMenu, footer, header { visibility: hidden; }
    .title-box { background: linear-gradient(135deg, #eff6ff 0%, #f5f3ff 100%); border: 1px solid #c7d2fe; border-radius: 12px; padding: 1rem; margin: 0.75rem 0; }
    .image-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.5rem; margin: 0.5rem 0; background: white; }
    .image-label { font-size: 12px; font-weight: 600; color: #6366f1; text-align: center; margin-top: 0.25rem; }
    .translate-header { display: flex; align-items: center; gap: 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 12px 16px; margin-bottom: 14px; }
    .translate-logo { width: 36px; height: 36px; border-radius: 10px; background: linear-gradient(135deg, #1677ff 0%, #36cfc9 100%); color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 16px; }
    .translate-title { font-size: 18px; font-weight: 700; }
    .translate-subtitle { font-size: 12px; color: #64748b; margin-top: 2px; }
    .form-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 12px 14px; margin-bottom: 12px; box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04); }
    .section-title { font-size: 14px; font-weight: 700; color: #111827; margin: 4px 0 10px 0; display: flex; align-items: center; gap: 8px; }
    .section-chip { font-size: 11px; color: #1677ff; background: #e6f4ff; border-radius: 999px; padding: 2px 8px; }
    .guide-card { background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%); border: 1px solid #e5e7eb; border-radius: 12px; padding: 10px 12px; font-size: 12px; }
    .thumb-grid img { border-radius: 8px; border: 1px solid #e5e7eb; }
    section[data-testid="stSidebar"] { background: #fbfbfd; }
    .stepper { display: flex; gap: 8px; flex-wrap: wrap; margin: 0.5rem 0 1rem; }
    .step { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px 10px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px; color: #334155; }
    .step-num { width: 18px; height: 18px; border-radius: 999px; background: #e2e8f0; color: #0f172a; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
    .step.active { background: linear-gradient(135deg, #e6f4ff 0%, #f0f5ff 100%); border-color: #91caff; color: #1e293b; }
    .step.active .step-num { background: #1677ff; color: #fff; }
    </style>""",
        unsafe_allow_html=True,
    )


def show_footer():
    today_images = get_today_generated_images_count()
    st.markdown(
        f"""
    <div class="footer">
        <p><strong>{APP_NAME}</strong> {APP_VERSION}</p>
        <p>📈 今日已出图: <strong>{today_images}</strong> 张</p>
        <p>作者: {APP_AUTHOR} | 商业服务: {APP_COMMERCIAL}</p>
        <p style="margin-top:0.75rem;font-size:11px;color:#94a3b8">© {datetime.now().year} All Rights Reserved.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def inject_browser_key_persistence():
    components.html(
        """
        <script>
        const mappings = [
          { label: "Gemini / Vertex API Key", storageKey: "temu_ai_studio_login_key" },
          { label: "中转站 API Key", storageKey: "temu_ai_studio_relay_key" },
          { label: "中转站 API 地址", storageKey: "temu_ai_studio_relay_base" }
        ];
        function applyPersistence() {
          const doc = window.parent.document;
          mappings.forEach((mapping) => {
            const inputs = doc.querySelectorAll(`input[aria-label="${mapping.label}"]`);
            if (!inputs.length) return;
            const saved = window.parent.localStorage.getItem(mapping.storageKey) || "";
            inputs.forEach((input) => {
              if (saved && !input.value) {
                input.value = saved;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
              }
              if (!input.dataset.persistBound) {
                input.addEventListener("input", () => {
                  window.parent.localStorage.setItem(mapping.storageKey, input.value || "");
                });
                input.dataset.persistBound = "1";
              }
            });
          });
        }
        applyPersistence();
        const observer = new MutationObserver(() => applyPersistence());
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        </script>
        """,
        height=0,
        width=0,
    )


# ==================== 初始化 ====================
def init_session():
    defaults = {
        "authenticated": False,
        "is_admin": False,
        "use_own_key": False,
        "own_api_key": "",
        "show_admin": False,
        "user_compliance_mode": "strict",
        "combo_anchor": None,
        "combo_reqs": [],
        "combo_images": [],
        "combo_generating": False,
        "combo_generation_done": False,
        "combo_results": [],
        "combo_errors": [],
        "combo_titles": [],
        "smart_generating": False,
        "smart_generation_done": False,
        "smart_results": [],
        "smart_errors": [],
        "smart_titles": [],
        "img_trans_results": [],
        "img_trans_errors": [],
        "img_trans_done": False,
        "img_trans_zip_cache": {"key": "", "bytes": b""},
        "img_trans_tokens_used": 0,
        "img_trans_source_items": [],
        "img_trans_last_options": {},
        "remember_login": False,
        "remember_role": None,
        "remember_until": 0,
        "session_tokens": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_working_session():
    keep_keys = {
        "authenticated",
        "is_admin",
        "use_own_key",
        "own_api_key",
        "remember_login",
        "remember_role",
        "remember_until",
        "user_id",
    }
    for k in list(st.session_state.keys()):
        if k not in keep_keys:
            del st.session_state[k]
    init_session()


def render_reference_tips():
    st.markdown(
        """
    <div class="help-section">
        <h4>💡 参考图选择建议</h4>
        <ul>
            <li>优先选择 <b>代表性</b> 图片：白底主图、带文字卖点图、场景/细节图、尺寸/标签图</li>
            <li>避免重复角度/水印/拼图/过度美化，文字尽量清晰无遮挡</li>
            <li>数量建议：每次 2-5 张参考图（过多会增加失败率和延迟）</li>
            <li>当前全局固定使用 Nano Banana 2 出图</li>
        </ul>
        <h4>🛠️ 稳定性建议</h4>
        <ul>
            <li>遇到 503/内部错误/长时间处理中：减少参考图、降低分辨率或分批提交</li>
            <li>点击侧边栏「清理会话缓存」后重试，必要时降低并发</li>
        </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )
    render_stepper(["上传", "翻译", "导出"], 1)


def render_translation_tips():
    st.markdown(
        """
    <div class="help-section">
        <h4>💡 图片建议</h4>
        <ul>
            <li>文字清晰、无遮挡、对比度足够，可显著提升 OCR 与翻译质量</li>
            <li>避免严重压缩或过小分辨率；批量过大请分批处理</li>
            <li>翻译出图固定 Nano Banana 2，建议推理级别选 minimal 提速</li>
        </ul>
        <h4>🛠️ 稳定性建议</h4>
        <ul>
            <li>遇到 503/内部错误/长时间处理中：降低分辨率、减少批次或稍后重试</li>
            <li>点击侧边栏「清理会话缓存」后重试，必要时降低并发</li>
            <li>结果页默认仅保留译后图下载链路，避免原图对照与格式切换导致卡顿</li>
        </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_stepper(steps, active_idx=1):
    items = []
    for i, label in enumerate(steps, start=1):
        active = "active" if i == active_idx else ""
        items.append(
            f'<div class="step {active}"><span class="step-num">{i}</span>{label}</div>'
        )
    st.markdown(f'<div class="stepper">{"".join(items)}</div>', unsafe_allow_html=True)


# ==================== 用户合规设置 ====================
def show_user_compliance():
    uid = get_user_id()
    comp = get_compliance()
    user_comp = comp.get("user_custom", {}).get(uid, {"blacklist": [], "whitelist": []})

    bl_str = st.text_area(
        "自定义黑名单 (逗号分隔)",
        ", ".join(user_comp.get("blacklist", [])),
        height=60,
        key="user_bl",
    )
    wl_str = st.text_area(
        "自定义白名单 (逗号分隔)",
        ", ".join(user_comp.get("whitelist", [])),
        height=60,
        key="user_wl",
    )

    if st.button("保存合规词", key="save_user_comp"):
        bl = [w.strip() for w in bl_str.split(",") if w.strip()]
        wl = [w.strip() for w in wl_str.split(",") if w.strip()]
        save_user_compliance(uid, bl, wl)
        st.success("✅ 已保存")


# ==================== 标题生成选项组件 ====================
def render_title_gen_option(prefix: str):
    title_templates = get_title_templates()
    enabled_templates = {
        k: v for k, v in title_templates.items() if v.get("enabled", True)
    }

    st.markdown("---")
    st.markdown("### 🏷️ 智能标题生成 (可选)")

    enable_title = st.checkbox(
        "📝 同时生成商品标题",
        key=f"{prefix}_enable_title",
        help="勾选后将在出图完成时一并生成中英双语标题",
    )

    if enable_title:
        st.markdown('<div class="title-box">', unsafe_allow_html=True)

        template_options = list(enabled_templates.keys())
        template_names = {k: v["name"] for k, v in enabled_templates.items()}

        selected_template = st.selectbox(
            "标题模板",
            options=template_options,
            format_func=lambda x: template_names.get(x, x),
            key=f"{prefix}_title_template",
            label_visibility="collapsed",
        )

        template_info = enabled_templates.get(selected_template, {})
        st.caption(f"📝 {template_info.get('desc', '')}")

        title_info = st.text_area(
            f"商品信息描述 (最多{MAX_TITLE_INFO_CHARS}字)",
            height=100,
            max_chars=MAX_TITLE_INFO_CHARS,
            key=f"{prefix}_title_info",
            placeholder="输入商品的详细信息，如：名称、材质、规格、特点、用途等...",
        )

        char_count = len(title_info) if title_info else 0
        st.caption(f"已输入 {char_count}/{MAX_TITLE_INFO_CHARS} 字符")

        st.markdown("</div>", unsafe_allow_html=True)

        return enable_title, title_info, selected_template

    return False, "", "default"


def display_generated_titles(titles: list, prefix: str = ""):
    """显示生成的中英双语标题"""
    if not titles:
        return

    st.markdown("### 🏷️ 生成的商品标题 (中英双语)")

    # 检测是否为中英双语格式 (6行)
    if len(titles) >= 6:
        labels = ["🔍 搜索优化", "💰 转化优化", "✨ 差异化"]
        for i in range(0, min(6, len(titles)), 2):
            title_idx = i // 2
            label = labels[title_idx] if title_idx < 3 else f"标题 {title_idx + 1}"
            en_title = titles[i] if i < len(titles) else ""
            cn_title = titles[i + 1] if i + 1 < len(titles) else ""

            # 计算英文字符数
            en_chars = len(en_title)
            char_status = (
                "✅" if MIN_TITLE_EN_CHARS <= en_chars <= MAX_TITLE_EN_CHARS else "⚠️"
            )

            st.markdown(
                f"""
            <div class="title-bilingual">
                <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem">
                    <span style="color:#6366f1;font-weight:600">{label}</span>
                    <span style="font-size:11px;color:#64748b">{char_status} EN: {en_chars}字符</span>
                </div>
                <div style="background:#e0e7ff;padding:0.5rem;border-radius:6px;margin-bottom:0.5rem">
                    <span style="font-size:11px;color:#4338ca">🇺🇸 English</span><br>
                    <span style="font-size:14px">{en_title}</span>
                </div>
                <div style="background:#fef3c7;padding:0.5rem;border-radius:6px">
                    <span style="font-size:11px;color:#92400e">🇨🇳 中文</span><br>
                    <span style="font-size:14px">{cn_title}</span>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        # 单语模式
        labels = ["🔍 搜索优化", "💰 转化优化", "✨ 差异化"]
        for i, t in enumerate(titles[:3]):
            label = labels[i] if i < 3 else f"标题 {i + 1}"
            st.markdown(
                f"""
            <div class="title-result">
                <span style="color:#6366f1;font-weight:600">{label}</span><br>
                <span style="font-size:15px">{t}</span>
            </div>
            """,
                unsafe_allow_html=True,
            )

    # 复制区域
    copy_text = (
        "\n\n".join(
            [
                f"Title {i // 2 + 1}:\nEN: {titles[i]}\nCN: {titles[i + 1]}"
                for i in range(0, min(6, len(titles)), 2)
            ]
        )
        if len(titles) >= 6
        else "\n".join(titles)
    )
    st.text_area(
        "📋 复制全部标题",
        copy_text,
        height=120,
        key=f"{prefix}_copy_titles_{random.randint(1000, 9999)}",
    )


# ==================== 类型选择组件 ====================
def render_type_selector(
    templates: dict, prefix: str, max_per_type: int = 3, max_total: int = 12
):
    def sel_key(tk):
        return f"{prefix}_sel_{tk}"

    def cnt_key(tk):
        return f"{prefix}_cnt_{tk}"

    enabled_templates = {k: v for k, v in templates.items() if v.get("enabled", True)}
    sorted_items = sorted(
        enabled_templates.items(), key=lambda x: x[1].get("order", 99)
    )

    for tk in enabled_templates:
        if sel_key(tk) not in st.session_state:
            st.session_state[sel_key(tk)] = False
        if cnt_key(tk) not in st.session_state:
            st.session_state[cnt_key(tk)] = 1

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button(
            "✅ 一键全选", key=f"{prefix}_select_all", use_container_width=True
        ):
            for tk in enabled_templates:
                st.session_state[sel_key(tk)] = True
            st.rerun()

    with col2:
        if st.button(
            "🔄 清空选择", key=f"{prefix}_clear_all", use_container_width=True
        ):
            for tk in enabled_templates:
                st.session_state[sel_key(tk)] = False
                st.session_state[cnt_key(tk)] = 1
            st.rerun()

    def calc_total():
        total = 0
        for tk in enabled_templates:
            if st.session_state.get(sel_key(tk), False):
                total += st.session_state.get(cnt_key(tk), 1)
        return total

    with col3:
        total = calc_total()
        color = "#ef4444" if total > max_total else "#10b981"
        st.markdown(
            f'<p style="text-align:right;font-size:14px;margin-top:8px">已选: <span style="color:{color};font-weight:700">{total}</span> / {max_total} 张</p>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    cols = st.columns(4)

    for i, (tk, info) in enumerate(sorted_items):
        with cols[i % 4]:
            is_selected = st.checkbox(
                f"{info.get('icon', '📷')} {info['name']}", key=sel_key(tk)
            )

            count_options = list(range(1, max_per_type + 1))
            current_count = st.session_state.get(cnt_key(tk), 1)
            if current_count not in count_options:
                current_count = 1
            current_index = count_options.index(current_count)

            st.selectbox(
                "数量",
                options=count_options,
                index=current_index,
                key=cnt_key(tk),
                label_visibility="collapsed",
                disabled=not is_selected,
            )
            st.caption(info.get("desc", ""))

    result = {}
    for tk in enabled_templates:
        if st.session_state.get(sel_key(tk), False):
            result[tk] = st.session_state.get(cnt_key(tk), 1)

    return result, calc_total()


# ==================== Gemini 3 高级设置 ====================
def render_gemini3_settings(prefix: str, model_key: str):
    model_info = MODELS.get(model_key, MODELS[PRIMARY_IMAGE_MODEL])
    supports_thinking = model_info.get("supports_thinking", False)

    st.markdown("#### ⚙️ 高级设置")

    if supports_thinking:
        c1, c2, c3 = st.columns(3)
    else:
        c1, c2 = st.columns(2)

    with c1:
        aspect = st.selectbox("📐 宽高比", ASPECT_RATIOS, key=f"{prefix}_aspect")

    with c2:
        available_res = model_info.get("resolutions", ["1K"])
        size = st.selectbox("🖼️ 分辨率", available_res, key=f"{prefix}_size")

    thinking_level = "minimal"  # 默认值

    if supports_thinking:
        with c3:
            thinking_levels = model_info.get("thinking_levels", ["low", "high"])
            default_thinking = model_info.get("default_thinking", "minimal")
            default_idx = (
                thinking_levels.index(default_thinking)
                if default_thinking in thinking_levels
                else 0
            )

            thinking_level = st.selectbox(
                "🧠 推理深度",
                thinking_levels,
                index=default_idx,
                format_func=lambda x: THINKING_LEVEL_DESC.get(x, x),
                key=f"{prefix}_thinking_level",
                help="Nano Banana 2 支持 minimal/high，minimal 更快",
            )
    else:
        st.caption("💡 当前模型不支持推理深度调节")

    return aspect, size, thinking_level


def render_image_engine_selector(prefix: str, settings: dict):
    default_provider = settings.get("default_image_provider", "Gemini")
    provider = st.radio(
        "出图引擎",
        ["Gemini", "中转站"],
        index=0 if default_provider == "Gemini" else 1,
        horizontal=True,
        key=f"{prefix}_image_provider",
    )
    relay_model = settings.get("relay_default_image_model", "imagine_x_1")
    relay_key = ""
    relay_base = settings.get("relay_api_base", RELAY_API_BASE)
    if provider == "Gemini":
        st.caption(f"Gemini 默认模型：{MODELS[PRIMARY_IMAGE_MODEL]['name']}")
    else:

        def relay_model_format(model_id: str):
            status = RELAY_MODEL_STATUS.get(model_id, {})
            suffix = status.get("label", "未知")
            return f"{model_id} · {suffix}"

        relay_model = st.selectbox(
            "中转站模型",
            list(RELAY_IMAGE_MODELS.keys()),
            index=list(RELAY_IMAGE_MODELS.keys()).index(relay_model)
            if relay_model in RELAY_IMAGE_MODELS
            else 0,
            format_func=relay_model_format,
            key=f"{prefix}_relay_model",
        )
        relay_key = st.text_input(
            "中转站 API Key",
            type="password",
            placeholder="sk-...",
            key=f"{prefix}_relay_key",
        ).strip()
        relay_base = (
            st.text_input(
                "中转站 API 地址",
                value=relay_base,
                placeholder="https://newapi.aisonnet.org/v1",
                key=f"{prefix}_relay_base",
            )
            .strip()
            .rstrip("/")
        )
        status = RELAY_MODEL_STATUS.get(relay_model, {})
        if status:
            st.markdown(
                f"<div class='guide-card'><strong style='color:{status.get('color', '#1677ff')}'>{status.get('label', '未知')}</strong><br>{status.get('note', '')}</div>",
                unsafe_allow_html=True,
            )
        st.caption("支持前台直接改 API 地址和 API Key；浏览器会自动记住。")
        st.caption("当前中转站出图仅接管图片生成，图需分析/标题仍优先走 Gemini。")
    return provider, relay_model, relay_key, relay_base


def render_relay_config_panel(prefix: str, settings: dict, expanded: bool = False):
    with st.expander("🛰️ 中转站配置", expanded=expanded):
        relay_base = (
            st.text_input(
                "中转站 API 地址",
                value=settings.get("relay_api_base", RELAY_API_BASE),
                placeholder="https://newapi.aisonnet.org/v1",
                key=f"{prefix}_relay_base_panel",
            )
            .strip()
            .rstrip("/")
        )
        relay_key = st.text_input(
            "中转站 API Key",
            type="password",
            placeholder="sk-...",
            key=f"{prefix}_relay_key_panel",
        ).strip()
        relay_model = st.selectbox(
            "测试模型",
            list(RELAY_IMAGE_MODELS.keys()),
            index=list(RELAY_IMAGE_MODELS.keys()).index(
                settings.get("relay_default_image_model", "imagine_x_1")
            )
            if settings.get("relay_default_image_model", "imagine_x_1")
            in RELAY_IMAGE_MODELS
            else 0,
            format_func=lambda model_id: (
                f"{model_id} · {RELAY_MODEL_STATUS.get(model_id, {}).get('label', '未知')}"
            ),
            key=f"{prefix}_relay_test_model",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "测试连接", key=f"{prefix}_relay_probe", use_container_width=True
            ):
                ok, message = probe_relay_api(relay_base, relay_key)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
        with c2:
            if st.button(
                "测试当前模型",
                key=f"{prefix}_relay_probe_model",
                use_container_width=True,
            ):
                ok, message = probe_relay_api(relay_base, relay_key, relay_model)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
        st.caption("这里的输入只保存在当前浏览器本地，不写入服务端文件。")


def render_image_translate_settings(
    prefix: str, model_key: str, default_size: str = "1K"
):
    model_info = MODELS.get(model_key, MODELS[PRIMARY_IMAGE_MODEL])
    supports_thinking = model_info.get("supports_thinking", False)
    st.markdown("#### ⚙️ 翻译出图设置")
    cols = st.columns(2) if supports_thinking else st.columns(1)
    with cols[0]:
        available_res = model_info.get("resolutions", ["1K"])
        default_idx = (
            available_res.index(default_size) if default_size in available_res else 0
        )
        size = st.selectbox(
            "🖼️ 输出分辨率", available_res, index=default_idx, key=f"{prefix}_size"
        )
    thinking_level = "minimal"
    if supports_thinking:
        with cols[1]:
            thinking_levels = model_info.get("thinking_levels", ["low", "high"])
            default_thinking = model_info.get("default_thinking", "minimal")
            default_idx = (
                thinking_levels.index(default_thinking)
                if default_thinking in thinking_levels
                else 0
            )
            thinking_level = st.selectbox(
                "🧠 推理深度",
                thinking_levels,
                index=default_idx,
                format_func=lambda x: THINKING_LEVEL_DESC.get(x, x),
                key=f"{prefix}_thinking_level",
            )
    else:
        st.caption("💡 当前模型不支持推理深度调节")
    return size, thinking_level


# ==================== 结果显示组件 ====================
def display_generation_results(
    results: list, errors: list, titles: list, tokens_used: int, prefix: str
):
    """显示生成结果 - 修复版"""

    # 显示Token消耗
    st.markdown(
        f'<div class="token-badge">🎯 消耗: {tokens_used:,} tokens</div>',
        unsafe_allow_html=True,
    )

    # 显示错误
    if errors:
        with st.expander(f"⚠️ {len(errors)} 个错误", expanded=False):
            for err in errors:
                st.error(err)

    # 显示图片
    if results:
        st.markdown(f"### ✅ 成功生成 {len(results)} 张图片")

        # 使用columns显示图片
        cols = st.columns(min(len(results), 4))
        for i, item in enumerate(results):
            with cols[i % 4]:
                img = item.get("image")
                label = item.get("label", f"图片{i + 1}")
                filename = item.get("filename", f"image_{i + 1}.png")

                if img:
                    st.image(img, caption=label, use_container_width=True)
                    st.caption(f"📁 {filename}")

        # 下载按钮
        st.markdown("---")
        zip_bytes = create_zip_from_results(results, titles)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ 下载全部 (ZIP)",
                data=zip_bytes,
                file_name=f"images_{date.today()}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        with col2:
            # 持久化存储
            stype, retention, url, err = maybe_persist_and_upload(
                zip_bytes, f"images_{date.today()}.zip"
            )
            if url:
                st.link_button("🌐 云端下载链接", url, use_container_width=True)

        if stype == "temp":
            st.caption("⚠️ 临时文件：请立即下载保存")
        elif retention > 0:
            st.caption(f"📌 文件将保存 {retention} 天")

        st.balloons()
    else:
        st.warning("未能生成任何图片，请检查错误信息")

    # 显示标题
    if titles:
        st.markdown("---")
        display_generated_titles(titles, prefix)


# ==================== 登录页 ====================
def show_login():
    st.markdown(f'<div class="main-title">🍌 {APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<p style="text-align:center;color:#64748b;margin-bottom:1.5rem">{APP_VERSION} · {APP_AUTHOR}</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    features = [
        ("1", "批量出图", "批量参考图一键出图"),
        ("2", "快速出图", "更少步骤，直接生成"),
        ("3", "标题优化", "中英标题优化"),
        ("4", "图片翻译", "直接输出英文译后图"),
    ]
    for col, (icon, title, subtitle) in zip(cols, features):
        col.markdown(
            f'<div class="feature-card"><span class="feature-icon">{icon}</span><div class="feature-title">{title}</div><div class="feature-desc">{subtitle}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    bootstrap_runtime_config()
    s = get_settings()
    allow_user_passwordless_login = bool(s.get("allow_user_passwordless_login", False))

    if not _has_valid_system_key():
        with st.expander("🚀 系统服务初始化", expanded=True):
            st.info("系统服务尚未配置API Key")
            admin_pwd = st.text_input(
                "管理员密码", type="password", key="init_admin_pwd"
            )
            keys_text = st.text_area(
                "API Keys (每行一个)", height=120, placeholder="AIza... 或 AQ..."
            )
            c1, c2 = st.columns(2)
            with c1:
                new_user_pwd = st.text_input(
                    "用户密码",
                    value=s.get("user_password"),
                    type="password",
                    key="init_user_pwd",
                )
            with c2:
                new_admin_pwd = st.text_input(
                    "新管理员密码",
                    value=s.get("admin_password"),
                    type="password",
                    key="init_new_admin_pwd",
                )
            if st.button("✅ 保存并启用", type="primary", use_container_width=True):
                if admin_pwd != s.get("admin_password"):
                    st.error("管理员密码错误")
                else:
                    keys = [
                        k.strip() for k in (keys_text or "").splitlines() if k.strip()
                    ]
                    if not keys:
                        st.error("请至少填写1个API Key")
                    else:
                        data = get_api_keys()
                        data["keys"] = [{"key": k, "enabled": True} for k in keys]
                        data["current_index"] = 0
                        save_api_keys(data)
                        s["user_password"] = new_user_pwd or s.get("user_password")
                        s["admin_password"] = new_admin_pwd or s.get("admin_password")
                        save_settings(s)
                        st.success("已保存！")
                        st.rerun()

    t1, t2, t3 = st.tabs(["🔑 自己的API Key", "🎫 系统服务", "🛰️ 中转站配置"])

    with t1:
        st.markdown(
            '<div class="info-card"><strong>💡 自有 Key 模式</strong><br><span style="font-size:13px;color:#64748b">支持 Gemini API Key（AIza...）和 Vertex Express Key（AQ...）</span></div>',
            unsafe_allow_html=True,
        )
        key = st.text_input(
            "Gemini / Vertex API Key",
            type="password",
            placeholder="AIza... 或 AQ...",
            key="login_key",
        )
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("🚀 立即使用", type="primary", use_container_width=True):
                key = (key or "").strip()
                if key and (key.startswith("AIza") or key.startswith("AQ.")):
                    try:
                        create_genai_client(key)
                        st.session_state.authenticated = True
                        st.session_state.use_own_key = True
                        st.session_state.own_api_key = key
                        st.session_state.is_admin = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 验证失败: {str(e)[:80]}")
                else:
                    st.error("请输入有效的 API Key（`AIza...` 或 `AQ...`）")
        with c2:
            st.markdown(
                '<a href="https://aistudio.google.com/apikey" target="_blank" style="color:#6366f1;font-size:13px">🔗 获取 Gemini API Key →</a>',
                unsafe_allow_html=True,
            )

    with t2:
        st.markdown(
            '<div class="info-card"><strong>🎫 系统服务模式</strong></div>',
            unsafe_allow_html=True,
        )
        user_role_name = (
            "👤 普通用户（免密）" if allow_user_passwordless_login else "👤 普通用户"
        )
        role = st.radio(
            "身份", [user_role_name, "🛠️ 管理员"], horizontal=True, key="role_select"
        )

        # 记住登录（会话内，默认8小时）
        remember_default = st.session_state.get("remember_login", False)
        remember_login = st.checkbox(
            "记住本次登录（8小时）", value=remember_default, key="remember_login"
        )

        # 自动登录判断
        if (
            remember_login
            and st.session_state.get("remember_until", 0) > datetime.now().timestamp()
        ):
            if role.startswith("👤"):
                if (
                    _has_valid_system_key()
                    and st.session_state.get("remember_role") == "user"
                ):
                    st.session_state.authenticated = True
                    st.session_state.use_own_key = False
                    st.session_state.is_admin = False
                    st.rerun()
            else:
                if st.session_state.get("remember_role") == "admin":
                    st.session_state.authenticated = True
                    st.session_state.is_admin = True
                    st.session_state.use_own_key = False
                    st.rerun()

        if role.startswith("👤"):
            if allow_user_passwordless_login:
                st.success("✅ 已开启系统服务用户免密登录")
                if st.button("👤 直接进入", type="primary", use_container_width=True):
                    if not _has_valid_system_key():
                        st.warning("⚠️ 系统未配置API Key")
                    else:
                        st.session_state.authenticated = True
                        st.session_state.use_own_key = False
                        st.session_state.is_admin = False
                        if remember_login:
                            st.session_state.remember_role = "user"
                            st.session_state.remember_until = (
                                datetime.now().timestamp() + 8 * 3600
                            )
                        st.rerun()
            else:
                pwd = st.text_input("访问密码", type="password", key="login_pwd")
                if st.button("👤 用户登录", type="primary", use_container_width=True):
                    if not _has_valid_system_key():
                        st.warning("⚠️ 系统未配置API Key")
                    elif pwd == s.get("user_password"):
                        st.session_state.authenticated = True
                        st.session_state.use_own_key = False
                        st.session_state.is_admin = False
                        if remember_login:
                            st.session_state.remember_role = "user"
                            st.session_state.remember_until = (
                                datetime.now().timestamp() + 8 * 3600
                            )
                        st.rerun()
                    else:
                        st.error("密码错误")
        else:
            admin_pwd = st.text_input("管理员密码", type="password", key="admin_pwd")
            if st.button("🛠️ 进入后台", use_container_width=True):
                if admin_pwd == s.get("admin_password"):
                    st.session_state.authenticated = True
                    st.session_state.is_admin = True
                    st.session_state.use_own_key = False
                    if remember_login:
                        st.session_state.remember_role = "admin"
                        st.session_state.remember_until = (
                            datetime.now().timestamp() + 8 * 3600
                        )
                    st.rerun()
                else:
                    st.error("密码错误")

    with t3:
        st.markdown(
            '<div class="info-card"><strong>🛰️ 中转站入口</strong><br><span style="font-size:13px;color:#64748b">这里可以直接填写中转站 API 地址、API Key，并测试连通性。</span></div>',
            unsafe_allow_html=True,
        )
        render_relay_config_panel("login", s, expanded=True)

    show_footer()


# ==================== 智能组图页面 ====================
def show_combo_page():
    st.markdown('<div class="page-title">1 批量出图</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-card">适合批量卖点图、主图、尺寸图。按步骤完成即可。</div>',
        unsafe_allow_html=True,
    )

    s = get_settings()
    templates = get_templates()["combo_types"]
    api_key = (
        st.session_state.own_api_key
        if st.session_state.use_own_key
        else get_next_api_key()
    )

    if not api_key:
        st.error("⚠️ 无可用的API Key")
        return

    # 侧边栏
    with st.sidebar:
        st.markdown("#### 📊 任务状态")
        if st.session_state.combo_anchor:
            a = st.session_state.combo_anchor
            st.markdown(
                f'<div class="success-card" style="font-size:13px"><strong>🎯 {a.get("product_name_zh", "商品")}</strong><br><span style="color:#64748b">品类: {a.get("primary_category", "未识别")}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("📤 请先上传并分析商品")

        st.markdown("---")
        st.markdown("#### 🛡️ 合规模式")
        comp = get_compliance()
        mode_options = {
            k: v["name"] for k, v in comp["presets"].items() if v.get("enabled", True)
        }
        current_mode = st.session_state.get("user_compliance_mode", "strict")
        selected_mode = st.selectbox(
            "合规级别",
            list(mode_options.keys()),
            format_func=lambda x: mode_options[x],
            index=list(mode_options.keys()).index(current_mode)
            if current_mode in mode_options
            else 0,
            label_visibility="collapsed",
        )
        st.session_state.user_compliance_mode = selected_mode

        st.markdown("---")
        st.markdown("#### 🤖 出图模型")
        model_key = PRIMARY_IMAGE_MODEL
        image_provider, relay_model, relay_key, relay_base = (
            render_image_engine_selector("combo", s)
        )
        st.session_state.combo_model_key = model_key

        st.markdown("---")
        if st.session_state.use_own_key:
            st.success("🔑 无限额度")
        else:
            uid = get_user_id()
            _, used, limit = check_user_limit(uid)
            st.progress(min(used / limit, 1.0) if limit > 0 else 0)
            st.caption(f"今日: {used}/{limit}")

        if st.session_state.session_tokens > 0:
            st.markdown(
                f'<div class="token-badge">🎯 {st.session_state.session_tokens:,} tokens</div>',
                unsafe_allow_html=True,
            )
        active_api_key = (
            st.session_state.own_api_key
            if st.session_state.use_own_key
            else peek_system_api_key()
        )
        rate_hint = get_rate_limit_hint(active_api_key)
        st.caption(f"{rate_hint['provider']} · {rate_hint['note']}")

    # 检查是否有已完成的结果需要显示
    if st.session_state.combo_generation_done and st.session_state.combo_results:
        st.markdown("## 📸 生成结果")
        display_generation_results(
            st.session_state.combo_results,
            st.session_state.combo_errors,
            st.session_state.combo_titles,
            st.session_state.get("combo_tokens_used", 0),
            "combo",
        )

        if st.button("🔄 开始新任务", type="primary", use_container_width=True):
            # 重置状态
            st.session_state.combo_anchor = None
            st.session_state.combo_reqs = []
            st.session_state.combo_images = []
            st.session_state.combo_results = []
            st.session_state.combo_errors = []
            st.session_state.combo_titles = []
            st.session_state.combo_generation_done = False
            st.session_state.combo_generating = False
            for tk in templates.keys():
                if f"combo_sel_{tk}" in st.session_state:
                    del st.session_state[f"combo_sel_{tk}"]
                if f"combo_cnt_{tk}" in st.session_state:
                    del st.session_state[f"combo_cnt_{tk}"]
            st.rerun()

        show_footer()
        return

    # 正常的Tab流程
    tabs = st.tabs(
        ["📤 上传素材", "🎨 选择类型", "📝 图需文案", "🛡️ 合规检测", "🖼️ 生成出图"]
    )

    steps = ["上传素材", "选择类型", "图需文案", "合规检测", "生成出图"]

    # Tab 1: 上传
    with tabs[0]:
        render_stepper(steps, 1)
        render_reference_tips()

        files = st.file_uploader(
            "上传商品图片",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="combo_upload_unique",
        )

        if files:
            images = []
            display_count = min(len(files), 6)
            cols = st.columns(display_count)
            for i, f in enumerate(files[:display_count]):
                img = Image.open(f).convert("RGB")
                images.append(img)
                with cols[i]:
                    st.image(img, caption=f"图{i + 1}", use_container_width=True)
            for f in files[display_count:MAX_IMAGES]:
                images.append(Image.open(f).convert("RGB"))
            st.session_state.combo_images = images
            st.success(f"✅ 已加载 {len(images)} 张图片")
            ref_limit = recommended_ref_limit(model_key)
            if len(images) > ref_limit:
                st.warning(
                    f"已上传 {len(images)} 张，将仅使用前 {ref_limit} 张作为参考图（模型推荐上限）"
                )

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(
                "商品名称",
                max_chars=MAX_NAME_CHARS,
                key="combo_name",
                placeholder="例如: 不锈钢保温杯",
            )
        with c2:
            detail = st.text_input(
                "简要描述",
                max_chars=MAX_DETAIL_CHARS,
                key="combo_detail",
                placeholder="例如: 500ml双层真空",
            )
        tags = st.text_input(
            "产品标签 (逗号分隔)",
            key="combo_tags",
            placeholder="保温持久, 食品级, 大容量",
        )
        st.info("下一步：点击「AI分析商品」后进入「选择类型」。")

        btn_disabled = not st.session_state.combo_images
        if st.button(
            "🔍 AI分析商品",
            type="primary",
            use_container_width=True,
            disabled=btn_disabled,
        ):
            with st.spinner("🤖 AI正在分析..."):
                try:
                    client = GeminiClient(api_key, model_key)
                    anchor = client.analyze_product(
                        st.session_state.combo_images, name, detail
                    )
                    st.session_state.combo_anchor = anchor
                    st.session_state.combo_tags_list = [
                        t.strip() for t in tags.split(",") if t.strip()
                    ][:MAX_TAGS]
                    st.session_state.session_tokens += client.get_tokens_used()
                    st.success("✅ 分析完成！")
                    st.rerun()
                except Exception as e:
                    st.error(f"分析失败: {str(e)}")

    # Tab 2: 选择类型
    with tabs[1]:
        render_stepper(steps, 2)
        if not st.session_state.combo_anchor:
            st.warning("👆 请先在「上传素材」完成商品分析")
        else:
            selected_types, total_count = render_type_selector(
                templates,
                prefix="combo",
                max_per_type=MAX_TYPE_COUNT,
                max_total=MAX_TOTAL_IMAGES,
            )

            if total_count > MAX_TOTAL_IMAGES:
                st.error(f"❌ 超出最大限制 ({MAX_TOTAL_IMAGES}张)")

            enable_title, title_info, title_template = render_title_gen_option("combo")
            st.info("下一步：生成图需文案后，进入「图需文案」查看并编辑。")

            st.markdown("---")
            if image_provider == "Gemini":
                aspect, size, thinking_level = render_gemini3_settings(
                    "combo", model_key
                )
            else:
                c1, c2 = st.columns(2)
                with c1:
                    aspect = st.selectbox(
                        "📐 宽高比", ASPECT_RATIOS, key="combo_aspect"
                    )
                with c2:
                    st.text_input(
                        "输出分辨率", value="1K", disabled=True, key="combo_relay_size"
                    )
                size = "1K"
                thinking_level = "minimal"
                st.caption("中转站默认按 1K 低并发出图。")

            can_generate = total_count > 0 and total_count <= MAX_TOTAL_IMAGES

            if st.button(
                "📝 AI生成图需文案",
                type="primary",
                use_container_width=True,
                disabled=not can_generate,
            ):
                with st.spinner("🤖 生成中..."):
                    try:
                        client = GeminiClient(api_key, model_key)
                        reqs = client.generate_requirements(
                            st.session_state.combo_anchor,
                            selected_types,
                            st.session_state.get("combo_tags_list", []),
                        )
                        reqs = normalize_requirements(reqs, selected_types, templates)
                        reqs = client.generate_en_copy(
                            st.session_state.combo_anchor, reqs
                        )
                        st.session_state.combo_reqs = reqs
                        st.session_state.session_tokens += client.get_tokens_used()
                        st.success("✅ 生成完成！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"生成失败: {str(e)}")

    # Tab 3: 图需文案
    with tabs[2]:
        render_stepper(steps, 3)
        reqs = st.session_state.combo_reqs
        if not reqs:
            st.info("👆 请先在「选择类型」生成图需文案")
        else:
            st.markdown(
                '<div class="help-section"><h4>✏️ 编辑提示</h4><ul><li>英文文案将直接出现在生成的图片上</li><li>避免使用认证词汇和绝对化用语</li></ul></div>',
                unsafe_allow_html=True,
            )
            for i, r in enumerate(reqs):
                info = templates.get(r.get("type_key", ""), {})
                with st.expander(
                    f"{info.get('icon', '📷')} {r.get('type_name', '')} #{r.get('index', 1)}",
                    expanded=(i < 2),
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**中文图需**")
                        r["topic"] = st.text_input(
                            "主题",
                            value=r.get("topic", ""),
                            max_chars=30,
                            key=f"topic_{i}",
                        )
                        r["scene"] = st.text_area(
                            "场景",
                            value=r.get("scene", ""),
                            max_chars=80,
                            height=80,
                            key=f"scene_{i}",
                        )
                    with c2:
                        st.markdown("**英文入图文案**")
                        r["headline"] = st.text_input(
                            "标题",
                            value=r.get("headline", ""),
                            max_chars=MAX_HEADLINE_CHARS,
                            key=f"hl_{i}",
                        )
                        r["subline"] = st.text_input(
                            "副标题",
                            value=r.get("subline", ""),
                            max_chars=MAX_SUBLINE_CHARS,
                            key=f"sl_{i}",
                        )
                        r["badge"] = st.text_input(
                            "徽章",
                            value=r.get("badge", ""),
                            max_chars=MAX_BADGE_CHARS,
                            key=f"bd_{i}",
                        )

    # Tab 4: 合规检测
    with tabs[3]:
        render_stepper(steps, 4)
        reqs = st.session_state.combo_reqs
        if not reqs:
            st.info("👆 请先生成图需文案")
        else:
            mode = st.session_state.get("user_compliance_mode", "strict")
            all_ok = True
            for i, r in enumerate(reqs):
                text = f"{r.get('headline', '')} {r.get('subline', '')} {r.get('badge', '')}"
                ok, _, note = check_compliance(text, mode)
                r["compliance_ok"] = ok
                if not ok:
                    all_ok = False
                info = templates.get(r.get("type_key", ""), {})
                with st.expander(
                    f"{'✅' if ok else '⚠️'} {info.get('icon', '')} {r.get('type_name', '')} #{r.get('index', 1)}",
                    expanded=not ok,
                ):
                    if ok:
                        st.success("✅ 通过")
                    else:
                        st.warning(f"⚠️ {note}")

            if all_ok:
                st.success("✅ 全部通过合规检测")

            if st.button(
                "🚀 确认并开始生成图片", type="primary", use_container_width=True
            ):
                st.session_state.combo_generating = True
                st.rerun()

    # Tab 5: 生成
    with tabs[4]:
        render_stepper(steps, 5)
        reqs = st.session_state.combo_reqs
        if not reqs:
            st.info("👆 请完成前面的步骤")
        elif not st.session_state.combo_generating:
            task_desc = f"**待生成: {len(reqs)} 张图片**"
            if st.session_state.get("combo_enable_title") and st.session_state.get(
                "combo_title_info"
            ):
                task_desc += " + **中英双语标题**"
            st.markdown(task_desc)
            if st.button("🚀 确认开始生成", type="primary", use_container_width=True):
                st.session_state.combo_generating = True
                st.rerun()
        else:
            # 执行生成
            model = PRIMARY_IMAGE_MODEL
            client = GeminiClient(api_key, model)
            anchor = st.session_state.combo_anchor
            aspect = st.session_state.get("combo_aspect", "1:1")
            size = st.session_state.get("combo_size", "1K")
            thinking_level = st.session_state.get("combo_thinking_level", "minimal")
            refs = st.session_state.combo_images

            progress = st.progress(0)
            status = st.empty()
            log_container = st.container()

            results = []
            errors = []

            for i, r in enumerate(reqs):
                type_key = r.get("type_key", "img")
                type_name = r.get("type_name", f"图片{i + 1}")
                type_info = templates.get(type_key, {})
                type_icon = type_info.get("icon", "📷")

                status.info(f"⏳ 生成: {type_icon} {type_name} ({i + 1}/{len(reqs)})")

                try:
                    prompt = client.compose_image_prompt(anchor, r, aspect)
                    s = get_settings()
                    enforce_en = bool(s.get("enforce_english_text", True))
                    en_retries = int(s.get("english_text_max_retries", 2))
                    if image_provider == "Gemini":
                        img = client.generate_image(
                            refs,
                            prompt,
                            aspect,
                            size,
                            thinking_level,
                            enforce_english=enforce_en,
                            max_attempts=en_retries,
                        )
                    else:
                        if not relay_key:
                            raise Exception("请先输入中转站 API Key")
                        relay_client = RelayImageClient(
                            relay_key,
                            relay_model,
                            base_url=relay_base
                            or s.get("relay_api_base", RELAY_API_BASE),
                        )
                        img = relay_client.generate_image(
                            refs,
                            prompt,
                            aspect,
                            size,
                            thinking_level,
                            enforce_english=enforce_en,
                            max_attempts=1,
                        )
                        if img is None:
                            raise Exception(
                                relay_client.get_last_error() or "中转站返回空图片"
                            )

                    if img:
                        # 带类型名称的文件名
                        filename = f"{str(i + 1).zfill(2)}_{type_name}.png"
                        label = f"{type_icon} {type_name}"

                        results.append(
                            {
                                "image": img,
                                "filename": filename,
                                "label": label,
                                "type_key": type_key,
                                "index": r.get("index", 1),
                            }
                        )

                        with log_container:
                            st.success(f"✅ {type_icon} {type_name} 生成成功")
                    else:
                        error_msg = client.get_last_error() or "返回空图片"
                        errors.append(f"{type_icon} {type_name}: {error_msg}")
                        with log_container:
                            st.error(f"❌ {type_icon} {type_name}: {error_msg}")

                except Exception as e:
                    error_msg = format_runtime_error_message(e, 220)
                    errors.append(f"{type_icon} {type_name}: {error_msg}")
                    with log_container:
                        st.error(f"❌ {type_icon} {type_name}: {error_msg}")

                progress.progress((i + 1) / len(reqs))

            # 生成标题
            generated_titles = []
            if st.session_state.get("combo_enable_title") and st.session_state.get(
                "combo_title_info"
            ):
                status.info("⏳ 生成中英双语标题...")
                try:
                    title_templates = get_title_templates()
                    template_key = st.session_state.get(
                        "combo_title_template", "default"
                    )
                    template_prompt = title_templates.get(template_key, {}).get(
                        "prompt", DEFAULT_TITLE_TEMPLATES["default"]["prompt"]
                    )
                    generated_titles = client.generate_titles(
                        st.session_state.combo_title_info, template_prompt
                    )
                except Exception as e:
                    with log_container:
                        st.warning(f"标题生成失败: {str(e)[:50]}")

            tokens_used = client.get_tokens_used()
            st.session_state.session_tokens += tokens_used

            # 保存结果到session_state
            st.session_state.combo_results = results
            st.session_state.combo_errors = errors
            st.session_state.combo_titles = generated_titles
            st.session_state.combo_tokens_used = tokens_used
            st.session_state.combo_generating = False
            st.session_state.combo_generation_done = True

            # 更新统计
            if results and not st.session_state.use_own_key:
                update_user_usage(get_user_id(), len(results), tokens_used)
                update_stats(len(results), tokens_used, image_count=len(results))

            if results:
                record_platform_usage_event_safe(
                    feature="combo_image_generation",
                    provider=image_provider,
                    model=PRIMARY_IMAGE_MODEL
                    if image_provider == "Gemini"
                    else (relay_model or "relay-image"),
                    request_count=len(reqs),
                    output_images=len(results),
                    tokens_used=tokens_used,
                    charge_source="own_key"
                    if st.session_state.use_own_key
                    else "system_pool",
                    actor_label=get_user_id(),
                    metadata_json={"titles_generated": len(generated_titles)},
                )

            status.success(f"✅ 完成！成功 {len(results)}/{len(reqs)} 张")

            # 刷新页面显示结果
            st.rerun()

    show_footer()


# ==================== 快速出图页面 ====================
def show_smart_page():
    st.markdown('<div class="page-title">2 快速出图</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-card">更少步骤，适合快速做单批图片。</div>',
        unsafe_allow_html=True,
    )

    s = get_settings()
    templates = get_templates()["smart_types"]
    api_key = (
        st.session_state.own_api_key
        if st.session_state.use_own_key
        else get_next_api_key()
    )

    if not api_key:
        st.error("⚠️ 无可用的API Key")
        return

    # 检查是否有已完成的结果
    if st.session_state.smart_generation_done and st.session_state.smart_results:
        st.markdown("## 📸 生成结果")
        display_generation_results(
            st.session_state.smart_results,
            st.session_state.smart_errors,
            st.session_state.smart_titles,
            st.session_state.get("smart_tokens_used", 0),
            "smart",
        )

        if st.button("🔄 开始新任务", type="primary", use_container_width=True):
            st.session_state.smart_results = []
            st.session_state.smart_errors = []
            st.session_state.smart_titles = []
            st.session_state.smart_generation_done = False
            st.session_state.smart_generating = False
            st.rerun()

        show_footer()
        return

    with st.expander("📖 使用说明"):
        st.markdown("简化流程，快速生成图片。可同时生成中英双语标题。")

    render_stepper(["上传素材", "选择类型", "生成出图"], 1)
    render_reference_tips()

    # 上传图片
    files = st.file_uploader(
        "上传商品图片",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="smart_upload_unique",
    )

    images = []
    if files:
        num_files = len(files)
        if num_files == 1:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                img = Image.open(files[0]).convert("RGB")
                images.append(img)
                st.image(img, caption="图1", width=100)
        else:
            cols = st.columns(min(num_files, 6))
            for i, f in enumerate(files[:6]):
                img = Image.open(f).convert("RGB")
                images.append(img)
                with cols[i]:
                    st.image(img, caption=f"图{i + 1}", width=80)
            for f in files[6:MAX_IMAGES]:
                images.append(Image.open(f).convert("RGB"))

        st.success(f"✅ 已加载 {len(images)} 张图片")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("商品名称 *", key="smart_name")
    with c2:
        material = st.text_input("材质", key="smart_material")

    st.markdown("---")

    render_stepper(["上传素材", "选择类型", "生成出图"], 2)
    selected_types, total_count = render_type_selector(
        templates, prefix="smart", max_per_type=5, max_total=20
    )

    enable_title, title_info, title_template = render_title_gen_option("smart")

    st.markdown("---")

    render_stepper(["上传素材", "选择类型", "生成出图"], 3)
    model = PRIMARY_IMAGE_MODEL
    image_provider, relay_model, relay_key, relay_base = render_image_engine_selector(
        "smart", s
    )
    if image_provider == "Gemini":
        aspect, size, thinking_level = render_gemini3_settings("smart", model)
    else:
        c1, c2 = st.columns(2)
        with c1:
            aspect = st.selectbox("📐 宽高比", ASPECT_RATIOS, key="smart_aspect")
        with c2:
            st.text_input(
                "输出分辨率", value="1K", disabled=True, key="smart_relay_size"
            )
        size = "1K"
        thinking_level = "minimal"
        st.caption("中转站默认按 1K 低并发出图。")

    can_gen = images and name and total_count > 0

    if st.button(
        "🚀 开始生成", type="primary", use_container_width=True, disabled=not can_gen
    ):
        client = GeminiClient(api_key, model)

        progress = st.progress(0)
        status = st.empty()
        log_container = st.container()

        # 先分析商品
        status.info("🤖 分析商品...")
        anchor = client.analyze_product(images, name, material or "")

        results = []
        errors = []
        done = 0

        for tk, cnt in selected_types.items():
            info = templates[tk]
            for idx in range(cnt):
                done += 1
                status.info(
                    f"⏳ 生成: {info['icon']} {info['name']} ({done}/{total_count})"
                )

                prompt = f"""Professional ecommerce product image.
Product: {name}
Material: {material or "not specified"}
Style: {info["name"]}
Features: {", ".join(anchor.get("visual_attrs", ["quality"]))}
CRITICAL: ALL text MUST be ENGLISH only. NO Chinese characters.
Aspect: {aspect}"""

                try:
                    s = get_settings()
                    enforce_en = bool(s.get("enforce_english_text", True))
                    en_retries = int(s.get("english_text_max_retries", 2))
                    if image_provider == "Gemini":
                        img = client.generate_image(
                            images,
                            prompt,
                            aspect,
                            size,
                            thinking_level,
                            enforce_english=enforce_en,
                            max_attempts=en_retries,
                        )
                    else:
                        if not relay_key:
                            raise Exception("请先输入中转站 API Key")
                        relay_client = RelayImageClient(
                            relay_key,
                            relay_model,
                            base_url=relay_base
                            or s.get("relay_api_base", RELAY_API_BASE),
                        )
                        img = relay_client.generate_image(
                            images,
                            prompt,
                            aspect,
                            size,
                            thinking_level,
                            enforce_english=enforce_en,
                            max_attempts=1,
                        )
                        if img is None:
                            raise Exception(
                                relay_client.get_last_error() or "中转站返回空图片"
                            )
                    if img:
                        filename = f"{str(done).zfill(2)}_{info['name']}.png"
                        label = f"{info['icon']} {info['name']}"
                        results.append(
                            {"image": img, "filename": filename, "label": label}
                        )
                        with log_container:
                            st.success(f"✅ {info['icon']} {info['name']} 生成成功")
                    else:
                        error_msg = client.get_last_error() or "返回空图片"
                        errors.append(f"{info['icon']} {info['name']}: {error_msg}")
                        with log_container:
                            st.error(f"❌ {info['icon']} {info['name']}: {error_msg}")
                except Exception as e:
                    error_msg = format_runtime_error_message(e, 220)
                    errors.append(f"{info['icon']} {info['name']}: {error_msg}")
                    with log_container:
                        st.error(f"❌ {info['icon']} {info['name']}: {error_msg}")

                progress.progress(done / total_count)

        # 生成标题
        generated_titles = []
        if enable_title and title_info:
            status.info("⏳ 生成中英双语标题...")
            try:
                title_templates_data = get_title_templates()
                template_prompt = title_templates_data.get(title_template, {}).get(
                    "prompt", DEFAULT_TITLE_TEMPLATES["default"]["prompt"]
                )
                generated_titles = client.generate_titles(title_info, template_prompt)
            except Exception as e:
                with log_container:
                    st.warning(f"标题生成失败: {str(e)[:50]}")

        tokens_used = client.get_tokens_used()
        st.session_state.session_tokens += tokens_used

        # 保存结果
        st.session_state.smart_results = results
        st.session_state.smart_errors = errors
        st.session_state.smart_titles = generated_titles
        st.session_state.smart_tokens_used = tokens_used
        st.session_state.smart_generation_done = True

        if results and not st.session_state.use_own_key:
            update_user_usage(get_user_id(), len(results), tokens_used)
            update_stats(len(results), tokens_used, image_count=len(results))

        if results:
            record_platform_usage_event_safe(
                feature="smart_image_generation",
                provider=image_provider,
                model=PRIMARY_IMAGE_MODEL
                if image_provider == "Gemini"
                else (relay_model or "relay-image"),
                request_count=total_count,
                output_images=len(results),
                tokens_used=tokens_used,
                charge_source="own_key"
                if st.session_state.use_own_key
                else "system_pool",
                actor_label=get_user_id(),
                metadata_json={"titles_generated": len(generated_titles)},
            )

        status.success(f"✅ 完成！成功 {len(results)}/{total_count} 张")
        st.rerun()

    show_footer()


# ==================== 标题生成页面 ====================
def show_title_page():
    st.markdown('<div class="page-title">3 标题优化</div>', unsafe_allow_html=True)

    api_key = (
        st.session_state.own_api_key
        if st.session_state.use_own_key
        else get_next_api_key()
    )

    if not api_key:
        st.error("⚠️ 无可用的API Key")
        return

    title_templates = get_title_templates()

    st.markdown(
        f"""<div class="help-section">
        <h4>🎯 输出规则</h4>
        <ul>
            <li><b>双语输出</b> - 每个标题同时生成英文和中文</li>
            <li><b>英文字符</b> - {MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS}字符</li>
            <li><b>三种策略</b> - 搜索优化/转化优化/差异化</li>
        </ul>
    </div>""",
        unsafe_allow_html=True,
    )

    # 输入模式
    st.markdown("### 📥 输入方式")
    input_mode = st.radio(
        "选择输入方式",
        ["📝 文字描述", "🖼️ 图片分析", "🔀 图片+文字"],
        horizontal=True,
        key="title_input_mode",
    )

    uploaded_images = []
    product_info = ""

    if input_mode in ["🖼️ 图片分析", "🔀 图片+文字"]:
        st.markdown("#### 🖼️ 上传商品图片")
        title_files = st.file_uploader(
            "上传图片",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="title_image_upload",
        )

        if title_files:
            cols = st.columns(min(len(title_files), 5))
            for i, f in enumerate(title_files[:5]):
                img = Image.open(f).convert("RGB")
                uploaded_images.append(img)
                with cols[i]:
                    st.image(img, caption=f"图{i + 1}", width=60)
            st.success(f"✅ 已加载 {len(uploaded_images)} 张图片")

    if input_mode in ["📝 文字描述", "🔀 图片+文字"]:
        st.markdown("### 📝 商品信息")
        product_info = st.text_area(
            "商品信息",
            height=150,
            max_chars=MAX_TITLE_INFO_CHARS,
            key="title_product_info",
            placeholder="请输入商品详细信息：名称、材质、规格、功能、用途等...",
        )

        if product_info:
            st.caption(f"已输入 {len(product_info)}/{MAX_TITLE_INFO_CHARS} 字符")

    st.markdown("---")
    st.markdown("### 📋 选择标题模板")

    enabled_templates = {
        k: v for k, v in title_templates.items() if v.get("enabled", True)
    }

    if input_mode == "🖼️ 图片分析":
        template_options = ["image_analysis"] + [
            k for k in enabled_templates.keys() if k != "image_analysis"
        ]
    else:
        template_options = ["custom"] + list(enabled_templates.keys())

    template_names = {"custom": "✏️ 自定义提示词"}
    template_names.update({k: v["name"] for k, v in enabled_templates.items()})

    default_idx = 0
    if input_mode == "🖼️ 图片分析" and "image_analysis" in template_options:
        default_idx = 0

    selected_template = st.selectbox(
        "模板",
        options=template_options,
        index=default_idx,
        format_func=lambda x: template_names.get(x, x),
        key="title_template_select",
        label_visibility="collapsed",
    )

    if selected_template == "custom":
        st.markdown("#### ✏️ 自定义提示词")
        custom_prompt = st.text_area(
            "提示词 ({product_info}为占位符)",
            height=200,
            key="custom_title_prompt",
            placeholder="Generate bilingual titles for: {product_info}",
        )
        final_prompt = (
            custom_prompt
            if custom_prompt
            else DEFAULT_TITLE_TEMPLATES["default"]["prompt"]
        )
    else:
        template_info = enabled_templates.get(selected_template, {})
        st.info(f"📝 {template_info.get('desc', '')}")
        final_prompt = template_info.get(
            "prompt", DEFAULT_TITLE_TEMPLATES["default"]["prompt"]
        )

    # 生成按钮
    can_generate = False
    if input_mode == "📝 文字描述":
        can_generate = product_info and len(product_info) >= 10
    elif input_mode == "🖼️ 图片分析":
        can_generate = len(uploaded_images) > 0
    else:
        can_generate = len(uploaded_images) > 0 or (
            product_info and len(product_info) >= 10
        )

    if st.button(
        "🚀 生成中英双语标题",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
    ):
        with st.spinner("🤖 AI生成中..."):
            try:
                client = GeminiClient(api_key)

                if input_mode == "🖼️ 图片分析" or (
                    input_mode == "🔀 图片+文字" and uploaded_images
                ):
                    titles = client.generate_titles_from_image(
                        uploaded_images, product_info or "", final_prompt
                    )
                else:
                    titles = client.generate_titles(product_info, final_prompt)

                if titles:
                    if not st.session_state.use_own_key:
                        update_user_usage(get_user_id(), 1, client.get_tokens_used())
                        update_stats(1, client.get_tokens_used(), image_count=0)

                    record_platform_usage_event_safe(
                        feature="title_optimization",
                        provider="Gemini",
                        model=PRIMARY_IMAGE_MODEL,
                        request_count=1,
                        output_images=0,
                        tokens_used=client.get_tokens_used(),
                        charge_source="own_key"
                        if st.session_state.use_own_key
                        else "system_pool",
                        actor_label=get_user_id(),
                        metadata_json={"titles_generated": len(titles)},
                    )

                    st.session_state.session_tokens += client.get_tokens_used()

                    st.markdown("---")
                    display_generated_titles(titles, "title")
                    st.markdown(
                        f'<div class="token-badge">🎯 消耗: {client.get_tokens_used():,} tokens</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("生成失败，请重试")
            except Exception as e:
                st.error(f"生成失败: {str(e)}")

    show_footer()


# ==================== 图片翻译页面 ====================
def show_image_translate_page():
    st.markdown(
        """
    <div class="translate-header">
        <div class="translate-logo">4</div>
        <div>
            <div class="translate-title">4 图片翻译</div>
            <div class="translate-subtitle">批量翻译 · 英文出图 · 简化下载</div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "上传图片后默认直接生成英文译后图。图片翻译当前固定走 Gemini / Vertex 图文链路。"
    )
    render_translation_tips()

    api_key = (
        st.session_state.own_api_key
        if st.session_state.use_own_key
        else get_next_api_key()
    )
    if not api_key:
        st.error("⚠️ 无可用的API Key")
        return
    s = get_settings()
    allowed_formats = parse_allowed_formats(
        s.get("translate_allowed_formats", "png,jpg,jpeg,webp,heic,heif")
    )
    max_input = int(s.get("translate_max_input", 200))
    batch_size = int(s.get("translate_batch_size", s.get("translate_max_upload", 20)))
    max_file_mb = float(s.get("translate_max_file_mb", 7))
    uid = get_user_id()

    bg_tasks = list_image_translate_bg_tasks(uid)
    if bg_tasks:
        st.markdown("### 🧵 后台任务")
        c_refresh, c_hint = st.columns([1, 3])
        with c_refresh:
            if st.button("刷新后台任务", key="img_trans_bg_refresh"):
                st.rerun()
        with c_hint:
            st.caption("已提交任务可在后台持续执行；你可继续上传并提交下一批。")
        status_label = {
            "queued": "排队中",
            "running": "执行中",
            "completed": "已完成",
            "failed": "失败",
        }
        for task in bg_tasks[:12]:
            task_id = task.get("id", "")
            task_status = task.get("status", "queued")
            total_items = int(task.get("total", 0) or 0)
            done_items = int(task.get("done", 0) or 0)
            c1, c2, c3, c4 = st.columns([1.8, 2.8, 1.6, 0.8])
            with c1:
                st.caption(f"任务ID: {task_id}")
            with c2:
                label = status_label.get(task_status, task_status)
                if task_status in ("queued", "running"):
                    st.write(f"{label} · {done_items}/{max(1, total_items)}")
                    if total_items > 0:
                        st.progress(min(1.0, done_items / total_items))
                elif task_status == "completed":
                    st.success(task.get("message", label))
                else:
                    st.error(task.get("error") or task.get("message") or label)
            with c3:
                if task_status == "completed":
                    if st.button("加载结果", key=f"img_trans_bg_load_{task_id}"):
                        result_data = task.get("result") or {}
                        st.session_state.img_trans_results = result_data.get(
                            "results", []
                        )
                        st.session_state.img_trans_errors = result_data.get(
                            "errors", []
                        )
                        st.session_state.img_trans_tokens_used = result_data.get(
                            "tokens_used", 0
                        )
                        st.session_state.img_trans_done = True
                        st.session_state.img_trans_zip_cache = {"key": "", "bytes": b""}
                        st.session_state.img_trans_source_items = result_data.get(
                            "source_items", []
                        )
                        st.session_state.img_trans_last_options = result_data.get(
                            "last_options", {}
                        )
                        st.rerun()
            with c4:
                if task_status in ("completed", "failed"):
                    if st.button("删除", key=f"img_trans_bg_del_{task_id}"):
                        remove_image_translate_bg_task(uid, task_id)
                        st.rerun()

    # 已完成结果展示
    if st.session_state.img_trans_done and st.session_state.img_trans_results:
        st.markdown("## 翻译结果")
        guide_cols = st.columns(3)
        with guide_cols[0]:
            st.markdown(
                '<div class="guide-card"><b>1 上传</b><br>支持批量图片，自动识别文本</div>',
                unsafe_allow_html=True,
            )
        with guide_cols[1]:
            st.markdown(
                '<div class="guide-card"><b>2 翻译</b><br>北美电商英文 + 合规词策略</div>',
                unsafe_allow_html=True,
            )
        with guide_cols[2]:
            st.markdown(
                '<div class="guide-card"><b>3 导出</b><br>勾选下载 / ZIP 压缩</div>',
                unsafe_allow_html=True,
            )
        if st.session_state.img_trans_errors:
            with st.expander(
                f"⚠️ {len(st.session_state.img_trans_errors)} 个错误", expanded=False
            ):
                for err in st.session_state.img_trans_errors:
                    st.error(err)

        results = st.session_state.img_trans_results
        translated_only = [r for r in results if r.get("translated")]
        text_blocks = []

        if translated_only:
            st.markdown("### 译后图速览")
            grid_cols = st.columns(6)
            for i, r in enumerate(translated_only):
                with grid_cols[i % 6]:
                    st.image(
                        r.get("translated"),
                        caption=f"{r.get('index', i + 1):02d}",
                        width=120,
                    )

            option_labels = []
            label_to_item = {}
            for r in translated_only:
                idx = r.get("index", 0)
                base = r.get("base_name", f"image_{idx:02d}")
                label = f"{idx:02d} - {base}"
                option_labels.append(label)
                label_to_item[label] = r

            selected_labels = st.multiselect(
                "勾选下载（集中选择）",
                options=option_labels,
                default=option_labels,
                key="img_trans_batch_select",
            )
            selected_results = [
                label_to_item[k] for k in selected_labels if k in label_to_item
            ]
            st.caption(
                f"已勾选 {len(selected_results)}/{len(translated_only)} 张译后图"
            )
            with st.expander("统计信息", expanded=False):
                st.write(f"总结果数: {len(results)}")
                st.write(f"译后图数量: {len(translated_only)}")
                st.write(
                    f"总 Token: {st.session_state.get('img_trans_tokens_used', 0):,}"
                )
        else:
            selected_results = []
            st.info("本次任务未生成译后图，可在下方重试失败项。")

        for i, r in enumerate(results, start=1):
            src_lines = r.get("extracted_lines") or []
            tgt_lines = r.get("translated_lines") or []
            if src_lines or tgt_lines:
                src_text = "\n".join(src_lines) if src_lines else "（未识别到文字）"
                tgt_text = "\n".join(tgt_lines) if tgt_lines else "（未生成翻译）"
                text_blocks.append(f"图{i}\n原文:\n{src_text}\n译文:\n{tgt_text}\n")

        if translated_only:
            preview_choice = st.selectbox(
                "单图详情（可选）",
                options=["不查看详情", *option_labels],
                key="img_trans_preview_choice",
            )
            if preview_choice != "不查看详情":
                picked = label_to_item.get(preview_choice)
                if picked:
                    idx = picked.get("index", 1)
                    st.markdown(f"### 图{idx} 详情")
                    st.image(picked.get("translated"), caption="翻译后", width=320)
                    st.download_button(
                        "下载该译后图",
                        data=get_translated_png_bytes(picked),
                        file_name=picked.get("filename", f"translated_{idx:02d}.png"),
                        mime="image/png",
                        key="img_trans_dl_preview",
                    )
                    if picked.get("compliance_hits"):
                        st.warning(
                            f"合规词命中: {', '.join(picked.get('compliance_hits'))}"
                        )
                    src_lines = picked.get("extracted_lines") or []
                    tgt_lines = picked.get("translated_lines") or []
                    if src_lines or tgt_lines:
                        src_text = (
                            "\n".join(src_lines) if src_lines else "（未识别到文字）"
                        )
                        tgt_text = (
                            "\n".join(tgt_lines) if tgt_lines else "（未生成翻译）"
                        )
                        with st.expander("文本对照", expanded=False):
                            st.text_area(
                                "识别文字 / 翻译结果",
                                f"原文:\n{src_text}\n\n译文:\n{tgt_text}",
                                height=140,
                                key="img_trans_text_preview",
                            )

        st.markdown("---")
        st.markdown("### 批量下载")
        scope = st.radio(
            "下载范围",
            ["仅勾选", "全部译后图"],
            horizontal=True,
            key="img_trans_dl_scope",
        )
        pack_items = selected_results if scope == "仅勾选" else translated_only
        zip_name = f"translated_images_{date.today()}.zip"

        if pack_items:
            pack_indices = sorted(
                [r.get("index", 0) for r in pack_items if r.get("translated")]
            )
            results_signature = "|".join(
                [
                    f"{r.get('index', 0)}:{1 if r.get('translated') else 0}"
                    for r in results
                ]
            )
            zip_cache_key = (
                f"{results_signature}__{','.join([str(i) for i in pack_indices])}"
            )
            zip_cache = st.session_state.get("img_trans_zip_cache", {})
            if zip_cache.get("key") != zip_cache_key:
                with st.spinner("正在打包 ZIP..."):
                    zip_cache = {
                        "key": zip_cache_key,
                        "bytes": create_translate_zip(pack_items),
                    }
                    st.session_state.img_trans_zip_cache = zip_cache
            zip_bytes = st.session_state.get("img_trans_zip_cache", {}).get(
                "bytes", b""
            )
            if zip_bytes:
                st.download_button(
                    "下载 ZIP",
                    data=zip_bytes,
                    file_name=zip_name,
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )
        else:
            st.caption("未选择任何译后图")

        if text_blocks:
            st.download_button(
                "下载翻译文本 (TXT)",
                data="\n\n".join(text_blocks).encode("utf-8"),
                file_name=f"translations_{date.today()}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown(
            f'<div class="token-badge">🎯 消耗: {st.session_state.get("img_trans_tokens_used", 0):,} tokens</div>',
            unsafe_allow_html=True,
        )

        opts = st.session_state.get("img_trans_last_options", {})
        source_items = st.session_state.get("img_trans_source_items", [])
        need_text_last = opts.get("need_text", False)
        need_image_last = opts.get("need_image", False)
        failed_indices = []
        for r in results:
            fail = False
            if need_image_last and not r.get("translated"):
                fail = True
            if need_text_last and not r.get("translated_lines"):
                fail = True
            if fail:
                failed_indices.append(r.get("index"))
        failed_indices = list(dict.fromkeys([i for i in failed_indices if i]))

        if failed_indices and st.button("重试失败项", use_container_width=True):
            image_retry_client = GeminiClient(
                api_key, opts.get("model_key", PRIMARY_IMAGE_MODEL)
            )
            text_retry_client = GeminiClient(
                api_key, opts.get("text_model_key", PRIMARY_IMAGE_MODEL)
            )
            source_prompt = LANGUAGE_PROMPT_NAMES.get(
                opts.get("source_lang", "auto"), "auto"
            )
            target_prompt = LANGUAGE_PROMPT_NAMES.get(
                opts.get("target_lang", "en"), "English"
            )
            style_choice = opts.get("style_choice", "北美电商英文（标准）")
            if style_choice == "北美电商英文（偏营销）":
                style_hint = "North American ecommerce listing English (Amazon-compliant, TEMU style), persuasive but professional, no slang or colloquial expressions, consistent terminology, US punctuation and units, avoid unsupported absolute claims"
            else:
                style_hint = "North American ecommerce listing English (Amazon-compliant, TEMU style), formal and professional, no slang or colloquial expressions, consistent terminology, US punctuation and units, avoid unsupported absolute claims"
            layout_hint = (
                "Strictly preserve layout typography and colors"
                if opts.get("keep_layout", True)
                else "Minor layout adjustments allowed to improve readability"
            )
            avoid_terms = opts.get("avoid_terms", [])
            size_strategy = opts.get("size_strategy", "保留原比例")
            ratio_method = opts.get("ratio_method", "补边(白色)")
            target_ratio = opts.get("target_ratio", "1:1")
            force_1k = opts.get("force_1k", False)
            size = opts.get("size", "1K")
            thinking_level = opts.get("thinking_level", "minimal")
            fast_mode_retry = bool(opts.get("fast_text_mode", True))
            force_english_retry = bool(opts.get("force_english_output", False))
            english_retry_max = max(1, min(5, int(opts.get("english_retry_max", 2))))
            cleanup_cn_overlay_retry = bool(opts.get("cleanup_cn_overlay", True))

            for idx in failed_indices:
                if not idx or idx - 1 >= len(source_items):
                    continue
                item = source_items[idx - 1]
                img = item.get("image")
                if img is None:
                    continue
                for r in results:
                    if r.get("index") == idx:
                        try:
                            if need_text_last:
                                if fast_mode_retry:
                                    merged = text_retry_client.extract_and_translate_image_text(
                                        img,
                                        source_lang=source_prompt,
                                        target_lang=target_prompt,
                                        style_hint=style_hint,
                                        avoid_terms=avoid_terms,
                                        enforce_english=force_english_retry,
                                        max_attempts=english_retry_max,
                                    )
                                    r["extracted_lines"] = merged.get(
                                        "source_lines", []
                                    )
                                    r["translated_lines"] = merged.get(
                                        "translated_lines", []
                                    )
                                else:
                                    extracted = (
                                        text_retry_client.extract_text_from_image(
                                            img, source_prompt
                                        )
                                    )
                                    r["extracted_lines"] = extracted.get("lines", [])
                                    r["translated_lines"] = (
                                        text_retry_client.translate_lines(
                                            r["extracted_lines"],
                                            source_lang=source_prompt,
                                            target_lang=target_prompt,
                                            style_hint=style_hint,
                                            avoid_terms=avoid_terms,
                                            enforce_english=force_english_retry,
                                            max_attempts=english_retry_max,
                                        )
                                    )
                                if (
                                    force_english_retry
                                    and r["extracted_lines"]
                                    and not r["translated_lines"]
                                ):
                                    raise Exception(
                                        text_retry_client.get_last_error()
                                        or "英文校验未通过，请重试或提高重试次数"
                                    )
                                if opts.get("enable_comp") and r["translated_lines"]:
                                    hits = []
                                    for line in r["translated_lines"]:
                                        hits.extend(
                                            find_compliance_hits(line, avoid_terms)
                                        )
                                    r["compliance_hits"] = list(dict.fromkeys(hits))
                            if need_image_last:
                                aspect = (
                                    closest_aspect_ratio(img.size)
                                    if size_strategy == "保留原比例"
                                    else target_ratio
                                )
                                prepared_img = img
                                if size_strategy != "保留原比例":
                                    prepared_img = apply_ratio_strategy(
                                        img, target_ratio, ratio_method
                                    )
                                model_size = (
                                    "1K"
                                    if (size_strategy == "强制1:1" and force_1k)
                                    else size
                                )
                                r["translated"] = image_retry_client.translate_image(
                                    prepared_img,
                                    target_lang=target_prompt,
                                    source_lang=source_prompt,
                                    style_hint=style_hint,
                                    layout_hint=layout_hint,
                                    aspect=aspect,
                                    size=model_size,
                                    thinking_level=thinking_level,
                                    avoid_terms=avoid_terms,
                                    enforce_english=force_english_retry,
                                    max_attempts=english_retry_max,
                                    cleanup_cn_overlay=cleanup_cn_overlay_retry,
                                )
                                if r["translated"]:
                                    if size_strategy != "保留原比例":
                                        r["translated"] = apply_ratio_strategy(
                                            r["translated"], target_ratio, ratio_method
                                        )
                                    if size_strategy == "强制1:1" and force_1k:
                                        r["translated"] = r["translated"].resize(
                                            (1024, 1024), Image.Resampling.LANCZOS
                                        )
                        except Exception:
                            pass
                        break
            st.session_state.img_trans_results = results
            st.session_state.img_trans_zip_cache = {"key": "", "bytes": b""}
            retry_tokens = (
                image_retry_client.get_tokens_used()
                + text_retry_client.get_tokens_used()
            )
            st.session_state.img_trans_tokens_used += retry_tokens
            st.session_state.session_tokens += retry_tokens
            st.rerun()

        if st.button("开始新任务", type="primary", use_container_width=True):
            st.session_state.img_trans_results = []
            st.session_state.img_trans_errors = []
            st.session_state.img_trans_done = False
            st.session_state.img_trans_tokens_used = 0
            st.session_state.img_trans_zip_cache = {"key": "", "bytes": b""}
            st.rerun()

        show_footer()
        return

    with st.expander("使用说明"):
        st.markdown("支持电商主图/详情图翻译。可仅翻译文本，或生成翻译后图片。")
        batch_hint = batch_size if batch_size > 0 else "自动"
        st.caption(
            f"单次最多 {max_input} 张（安全限制），系统自动分批（每批 {batch_hint} 张）。单张大小上限 {max_file_mb:g} MB，允许格式：{', '.join(allowed_formats) if allowed_formats else '未配置'}"
        )

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">上传图片 <span class="section-chip">批量</span></div>',
        unsafe_allow_html=True,
    )
    files = st.file_uploader(
        "上传图片",
        type=allowed_formats
        if allowed_formats
        else ["png", "jpg", "jpeg", "webp", "heic", "heif"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="img_translate_upload",
    )
    upload_items = []
    invalid_msgs = []
    if files:
        if max_input > 0 and len(files) > max_input:
            invalid_msgs.append(
                f"超过最大上传数量 {max_input} 张，仅处理前 {max_input} 张"
            )
            files = files[:max_input]
        for f in files:
            ext = Path(f.name).suffix.lower().lstrip(".")
            size_mb = (f.size / (1024 * 1024)) if hasattr(f, "size") else 0
            if allowed_formats and ext not in allowed_formats:
                invalid_msgs.append(f"{f.name}: 不支持的格式 ({ext})")
                continue
            if max_file_mb and size_mb > max_file_mb:
                invalid_msgs.append(
                    f"{f.name}: 文件过大 {size_mb:.2f}MB > {max_file_mb:g}MB"
                )
                continue
            try:
                img = Image.open(f).convert("RGB")
            except Exception:
                invalid_msgs.append(f"{f.name}: 无法读取图片")
                continue
            upload_items.append(
                {
                    "image": img,
                    "name": Path(f.name).stem,
                    "raw_name": f.name,
                    "ext": ext,
                }
            )

        if batch_size > 0 and len(upload_items) > batch_size:
            batches = (len(upload_items) + batch_size - 1) // batch_size
            st.info(
                f"已加入 {len(upload_items)} 张，将自动分 {batches} 批处理（每批 {batch_size} 张）"
            )

        if upload_items:
            cols = st.columns(min(len(upload_items), 6))
            for i, item in enumerate(upload_items[:6]):
                with cols[i]:
                    st.image(item["image"], caption=f"图{i + 1}", width=90)
            st.success(f"✅ 已加载 {len(upload_items)} 张图片")

        if invalid_msgs:
            with st.expander(f"⚠️ {len(invalid_msgs)} 个文件未进入队列", expanded=False):
                for msg in invalid_msgs:
                    st.error(msg)

    images = [item["image"] for item in upload_items]
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">基础设置 <span class="section-chip">语言 & 风格</span></div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    lang_keys = list(LANGUAGE_OPTIONS.keys())
    target_keys = [k for k in lang_keys if k != "auto"]
    with c1:
        source_lang = st.selectbox(
            "源语言",
            lang_keys,
            format_func=lambda x: LANGUAGE_OPTIONS[x],
            index=0,
            key="img_trans_source",
        )
    with c2:
        default_target = target_keys.index("en") if "en" in target_keys else 0
        target_lang = st.selectbox(
            "目标语言",
            target_keys,
            format_func=lambda x: LANGUAGE_OPTIONS[x],
            index=default_target,
            key="img_trans_target",
        )

    output_options = ["仅文本翻译", "生成翻译图片", "文本+翻译图片"]
    default_output = s.get("translate_default_output_mode", "生成翻译图片")
    output_mode = st.radio(
        "输出模式",
        output_options,
        index=output_options.index(default_output)
        if default_output in output_options
        else 1,
        horizontal=True,
        key="img_trans_mode",
    )
    fast_text_mode = st.checkbox(
        "极速文本链路（OCR+翻译合并）",
        value=bool(s.get("translate_fast_text_mode", True)),
        help="仅文本或文本+出图时，优先用单次请求完成提取+翻译，通常更快。",
        key="img_trans_fast_text_mode",
    )
    style_choice = st.radio(
        "翻译风格",
        ["北美电商英文（标准）", "北美电商英文（偏营销）"],
        horizontal=True,
        key="img_trans_style",
    )
    keep_layout = st.checkbox(
        "严格保持版式/字体/配色", value=True, key="img_trans_layout"
    )
    cleanup_cn_overlay_default = bool(s.get("translate_cleanup_chinese_overlay", True))
    cleanup_cn_overlay = st.checkbox(
        "清理中文覆盖文案/角标（默认开启）",
        value=cleanup_cn_overlay_default,
        help="清理非产品主体的中文叠字、角标、印章样式覆盖文字；品牌/商标 Logo 会保留。",
        key="img_trans_cleanup_cn_overlay",
    )
    target_is_english = target_lang == "en"
    force_english_default = bool(s.get("translate_force_english_output", True))
    retries_default = int(s.get("translate_english_max_retries", 2))
    retries_default = max(1, min(5, retries_default))
    force_english_output = st.checkbox(
        "强制英文规范输出（Amazon/TEMU）",
        value=force_english_default if target_is_english else False,
        disabled=not target_is_english,
        help="目标语言为 English 时，自动校验中文残留并触发重试。",
        key="img_trans_force_english",
    )
    english_retry_max = st.number_input(
        "英文校验重试次数",
        min_value=1,
        max_value=5,
        value=retries_default,
        disabled=not target_is_english,
        key="img_trans_english_retries",
    )
    if not target_is_english:
        force_english_output = False
        english_retry_max = 1
    st.markdown("</div>", unsafe_allow_html=True)

    need_text = output_mode in ["仅文本翻译", "文本+翻译图片"]
    need_image = output_mode in ["生成翻译图片", "文本+翻译图片"]

    size_strategy = s.get("translate_default_size_strategy", "保留原比例")
    ratio_method = s.get("translate_default_ratio_method", "补边(白色)")
    target_ratio = s.get("translate_default_ratio", "1:1")
    force_1k = False

    text_model_key = s.get("translate_text_model", PRIMARY_IMAGE_MODEL)
    if text_model_key not in MODELS:
        text_model_key = PRIMARY_IMAGE_MODEL
    text_workers = int(s.get("translate_text_workers", 2))
    text_workers = max(1, min(6, text_workers))

    if need_image:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">尺寸/比例策略 <span class="section-chip">输出</span></div>',
            unsafe_allow_html=True,
        )
        strategy_options = ["保留原比例", "强制1:1", "自定义比例"]
        size_strategy = st.radio(
            "尺寸策略",
            strategy_options,
            index=strategy_options.index(size_strategy)
            if size_strategy in strategy_options
            else 0,
            horizontal=True,
            key="img_trans_ratio_strategy",
        )
        ratio_method = st.selectbox(
            "处理方式",
            ["居中裁切", "补边(白色)", "补边(边缘取色)"],
            index=["居中裁切", "补边(白色)", "补边(边缘取色)"].index(ratio_method)
            if ratio_method in ["居中裁切", "补边(白色)", "补边(边缘取色)"]
            else 1,
            key="img_trans_ratio_method",
        )
        if size_strategy == "自定义比例":
            target_ratio = st.selectbox(
                "目标比例",
                ASPECT_RATIOS,
                index=ASPECT_RATIOS.index(target_ratio)
                if target_ratio in ASPECT_RATIOS
                else 0,
                key="img_trans_ratio",
            )
        elif size_strategy == "强制1:1":
            target_ratio = "1:1"
            force_1k = st.checkbox(
                "强制 1K (1024×1024)", value=True, key="img_trans_force_1k"
            )
        st.markdown("</div>", unsafe_allow_html=True)

    model_key = None
    size = "1K"
    thinking_level = "minimal"
    if need_image:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">翻译出图模型 <span class="section-chip">模型</span></div>',
            unsafe_allow_html=True,
        )
        s = get_settings()
        model_key = PRIMARY_IMAGE_MODEL
        st.caption(f"当前固定模型：{MODELS[model_key]['name']}")
        size, thinking_level = render_image_translate_settings(
            "img_trans", model_key, s.get("translate_default_resolution", "1K")
        )
        st.caption(
            f"文本链路模型: {MODELS.get(text_model_key, {}).get('name', text_model_key)}"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">文本翻译模型 <span class="section-chip">速度优先</span></div>',
            unsafe_allow_html=True,
        )
        text_model_key = PRIMARY_IMAGE_MODEL
        st.caption(f"当前固定模型：{MODELS[text_model_key]['name']}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">合规词策略 <span class="section-chip">风险控制</span></div>',
        unsafe_allow_html=True,
    )
    enable_comp = st.checkbox("启用合规词处理", value=True, key="img_trans_comp_enable")
    comp_strategy = st.radio(
        "合规词策略",
        ["保留", "追加", "模板"],
        horizontal=True,
        key="img_trans_comp_strategy",
    )

    all_tpls, enabled_tpls = get_translate_compliance_templates()
    tpl_keys = list(enabled_tpls.keys()) if enabled_tpls else ["default"]
    default_tpl = s.get("translate_default_compliance_template", "default")
    if default_tpl not in tpl_keys:
        default_tpl = tpl_keys[0]
    selected_tpl = default_tpl
    user_words_text = ""
    if comp_strategy == "模板":
        selected_tpl = st.selectbox(
            "选择模板",
            tpl_keys,
            format_func=lambda x: enabled_tpls.get(x, all_tpls.get(x, {})).get(
                "name", x
            ),
            index=tpl_keys.index(default_tpl),
            key="img_trans_comp_tpl",
        )
        user_words_text = st.text_area(
            "追加合规词 (可选)", height=80, key="img_trans_comp_user_words_tpl"
        )
    elif comp_strategy == "追加":
        user_words_text = st.text_area(
            "追加合规词", height=80, key="img_trans_comp_user_words"
        )

    user_words = parse_compliance_words(user_words_text)
    base_words = []
    if comp_strategy in ("保留", "追加"):
        base_words = all_tpls.get(default_tpl, {}).get("words", [])
    elif comp_strategy == "模板":
        base_words = all_tpls.get(selected_tpl, {}).get("words", [])
    effective_words = list(dict.fromkeys(base_words + user_words))

    if enable_comp:
        with st.expander("当前生效合规词", expanded=False):
            if effective_words:
                st.write("、".join(effective_words))
            else:
                st.caption("暂无合规词")
    st.markdown("</div>", unsafe_allow_html=True)

    run_mode = st.radio(
        "执行方式",
        ["前台处理（当前页等待）", "后台排队（可并发）"],
        index=0,
        horizontal=True,
        key="img_trans_run_mode",
    )
    st.caption(
        f"当前后台并发上限：{int(s.get('translate_bg_max_concurrent', 2))}（管理员可调整）"
    )

    can_run = bool(upload_items)
    start_label = "提交后台任务" if run_mode.startswith("后台") else "开始处理"
    if st.button(
        start_label, type="primary", use_container_width=True, disabled=not can_run
    ):
        if not upload_items:
            st.warning("请先上传图片")
            return

        if not st.session_state.use_own_key:
            allowed, used, limit = check_user_limit(uid)
            if not allowed or (limit > 0 and used + len(upload_items) > limit):
                st.error(f"⚠️ 今日额度不足 (已用 {used}/{limit})")
                return

        avoid_terms = effective_words if enable_comp else []
        enforce_english_output = bool(force_english_output) and (target_lang == "en")
        english_retry_max = max(1, min(5, int(english_retry_max)))

        last_options = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "style_choice": style_choice,
            "keep_layout": keep_layout,
            "fast_text_mode": fast_text_mode,
            "text_model_key": text_model_key,
            "text_workers": text_workers,
            "need_text": need_text,
            "need_image": need_image,
            "size_strategy": size_strategy,
            "ratio_method": ratio_method,
            "target_ratio": target_ratio,
            "force_1k": force_1k,
            "model_key": model_key or PRIMARY_IMAGE_MODEL,
            "size": size,
            "thinking_level": thinking_level,
            "enable_comp": enable_comp,
            "avoid_terms": avoid_terms,
            "force_english_output": enforce_english_output,
            "english_retry_max": english_retry_max,
            "cleanup_cn_overlay": cleanup_cn_overlay,
        }
        job_options = {**last_options, "batch_size": batch_size}

        if run_mode.startswith("后台"):
            try:
                bg_task_id = submit_image_translate_bg_task(
                    uid,
                    {
                        "owner_id": uid,
                        "api_key": api_key,
                        "upload_items": upload_items,
                        "options": job_options,
                        "last_options": last_options,
                        "charge_usage": not st.session_state.use_own_key,
                    },
                    max_concurrent=int(s.get("translate_bg_max_concurrent", 2)),
                )
                st.success(f"✅ 已提交后台任务：{bg_task_id}")
                st.info("你可以继续提交下一批任务，完成后在“后台任务”里加载结果。")
                st.rerun()
            except Exception as e:
                st.error(format_runtime_error_message(e, 220))
            return

        progress = st.progress(0)
        status = st.empty()
        log_container = st.empty()
        total = len(upload_items)
        status.info(format_translate_status(0, max(1, total), "处理中"))

        def progress_cb(current, task_total, phase):
            safe_total = max(1, int(task_total or 1))
            safe_current = max(0, int(current or 0))
            progress.progress(min(1.0, safe_current / safe_total))
            status.info(format_translate_status(safe_current, safe_total, phase))

        def log_cb(msg):
            if msg:
                log_container.info(msg)

        results, errors, tokens_used = execute_image_translate_workload(
            api_key, upload_items, job_options, progress_cb=progress_cb, log_cb=log_cb
        )

        st.session_state.session_tokens += tokens_used
        st.session_state.img_trans_results = results
        st.session_state.img_trans_errors = errors
        st.session_state.img_trans_tokens_used = tokens_used
        st.session_state.img_trans_done = True
        st.session_state.img_trans_zip_cache = {"key": "", "bytes": b""}
        st.session_state.img_trans_source_items = upload_items
        st.session_state.img_trans_last_options = last_options

        if results and not st.session_state.use_own_key:
            update_user_usage(uid, len(results), tokens_used)
            update_stats(
                len(results), tokens_used, image_count=count_generated_images(results)
            )

        if results:
            record_platform_usage_event_safe(
                feature="image_translate",
                provider="Gemini",
                model=model_key or PRIMARY_IMAGE_MODEL,
                request_count=len(upload_items),
                output_images=count_generated_images(results),
                tokens_used=tokens_used,
                charge_source="own_key"
                if st.session_state.use_own_key
                else "system_pool",
                actor_label=uid,
                metadata_json={"mode": "foreground", "errors": len(errors)},
            )

        status.success(f"✅ 完成！成功 {len(results) - len(errors)}/{len(results)} 张")
        st.rerun()

    show_footer()


# ==================== 管理后台 ====================
def show_admin():
    if not st.session_state.get("is_admin"):
        st.error("仅管理员可访问后台")
        return

    st.markdown('<div class="page-title">⚙️ 管理后台</div>', unsafe_allow_html=True)

    s = get_settings()
    tabs = st.tabs(
        [
            "📊 基础设置",
            "🔐 密码配额",
            "🔑 API Keys",
            "🛡️ 合规设置",
            "📝 提示词",
            "🏷️ 标题模板",
            "🎨 组图模板",
            "👥 用户管理",
            "🏦 钱包账本",
            "🎟️ 兑换码",
        ]
    )

    with tabs[0]:
        st.markdown("### 📊 系统统计")
        stats = get_stats()
        users = get_users()
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("总生成次数", stats.get("total", 0))
        with c2:
            st.metric(
                "今日生成", stats.get("daily", {}).get(date.today().isoformat(), 0)
            )
        with c3:
            st.metric("Token消耗", f"{stats.get('tokens_total', 0):,}")
        with c4:
            st.metric("用户数", len(users))
        with c5:
            st.metric("累计出图张数", stats.get("images_total", 0))
        with c6:
            st.metric(
                "今日出图张数",
                stats.get("daily_images", {}).get(date.today().isoformat(), 0),
            )

        st.markdown("---")
        st.markdown("### 🗄️ 文件存储")
        st.selectbox(
            "存储类型",
            ["local", "s3"],
            index=0 if s.get("file_storage_type", "local") == "local" else 1,
            key="storage_type",
        )
        s["file_storage_type"] = st.session_state.get("storage_type", "local")
        s["file_retention_days"] = st.number_input(
            "保留天数", 1, 365, s.get("file_retention_days", 7)
        )
        s["file_storage_path"] = st.text_input(
            "存储路径", s.get("file_storage_path", "/app/data/files")
        )

        if s["file_storage_type"] == "s3":
            with st.expander("S3配置"):
                s["s3_endpoint"] = st.text_input("Endpoint", s.get("s3_endpoint", ""))
                s["s3_bucket"] = st.text_input("Bucket", s.get("s3_bucket", ""))
                s["s3_region"] = st.text_input("Region", s.get("s3_region", ""))
                s["s3_access_key"] = st.text_input(
                    "Access Key", s.get("s3_access_key", ""), type="password"
                )
                s["s3_secret_key"] = st.text_input(
                    "Secret Key", s.get("s3_secret_key", ""), type="password"
                )

        if st.button("💾 保存", type="primary", key="save_basic"):
            save_settings(s)
            st.success("✅ 已保存")

    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            s["user_password"] = st.text_input(
                "用户密码", s.get("user_password"), type="password"
            )
            s["daily_limit_user"] = st.number_input(
                "普通用户日限额", 1, 1000, s.get("daily_limit_user", 30)
            )
        with c2:
            s["admin_password"] = st.text_input(
                "管理员密码", s.get("admin_password"), type="password"
            )
            s["daily_limit_vip"] = st.number_input(
                "VIP日限额", 1, 1000, s.get("daily_limit_vip", 100)
            )
        s["allow_user_passwordless_login"] = st.checkbox(
            "允许系统服务用户免密登录",
            value=bool(s.get("allow_user_passwordless_login", False)),
        )
        if _parse_env_bool("ALLOW_PASSWORDLESS_USER_LOGIN") is not None:
            st.info(
                "检测到环境变量 `ALLOW_PASSWORDLESS_USER_LOGIN`，重启后会按环境变量值覆盖。"
            )
        if (os.getenv("ADMIN_PASSWORD_FIXED") or "").strip() or (
            os.getenv("USER_PASSWORD_FIXED") or ""
        ).strip():
            st.info("检测到固定密码环境变量，重启后会自动注入。")

        st.markdown("---")
        st.markdown("### 🤖 默认设置")
        c1, c2, c3 = st.columns(3)
        with c1:
            s["default_model"] = PRIMARY_IMAGE_MODEL
            st.text_input(
                "默认模型",
                MODELS[PRIMARY_IMAGE_MODEL]["name"],
                disabled=True,
                key="admin_default_model_locked",
            )
        with c2:
            s["default_resolution"] = "1K"
            st.selectbox(
                "默认分辨率", ["1K"], index=0, key="admin_default_resolution_locked"
            )
        with c3:
            s["default_aspect"] = st.selectbox(
                "默认宽高比",
                ASPECT_RATIOS,
                index=ASPECT_RATIOS.index(s.get("default_aspect", "1:1")),
            )
        s["default_image_provider"] = st.selectbox(
            "默认出图引擎",
            ["Gemini", "中转站"],
            index=0 if s.get("default_image_provider", "Gemini") == "Gemini" else 1,
        )
        if s["default_image_provider"] == "中转站":
            s["relay_default_image_model"] = st.selectbox(
                "默认中转站模型",
                list(RELAY_IMAGE_MODELS.keys()),
                index=list(RELAY_IMAGE_MODELS.keys()).index(
                    s.get("relay_default_image_model", "imagine_x_1")
                )
                if s.get("relay_default_image_model", "imagine_x_1")
                in RELAY_IMAGE_MODELS
                else 0,
            )
        st.caption("出图模型已全局锁定为 Nano Banana 2。")
        st.markdown("---")
        s["enforce_english_text"] = st.checkbox(
            "强制英文文本校验（自动重试）", value=s.get("enforce_english_text", False)
        )
        s["english_text_max_retries"] = st.number_input(
            "英文校验最大重试次数", 1, 5, int(s.get("english_text_max_retries", 1))
        )
        st.caption("关闭可减少 Token 消耗并提升速度；建议通过提示词约束英文输出。")

        if st.button("💾 保存", type="primary", key="save_pwd"):
            save_settings(s)
            st.success("✅ 已保存")

        st.markdown("---")
        st.markdown("### 🈯 图片翻译默认设置")
        t_c1, t_c2, t_c3 = st.columns(3)
        with t_c1:
            s["translate_max_input"] = st.number_input(
                "单次最大上传量（硬限制）", 1, 900, s.get("translate_max_input", 200)
            )
            s["translate_batch_size"] = st.number_input(
                "自动分批大小（非限制）", 1, 200, s.get("translate_batch_size", 20)
            )
            s["translate_max_file_mb"] = st.number_input(
                "单张大小上限 (MB)", 1, 30, s.get("translate_max_file_mb", 7)
            )
            st.caption("超过最大上传量会被截断；超过分批大小将自动拆批处理。")
        with t_c2:
            s["translate_allowed_formats"] = st.text_input(
                "允许格式 (逗号分隔)",
                s.get("translate_allowed_formats", "png,jpg,jpeg,webp,heic,heif"),
            )
            s["translate_default_output_mode"] = st.selectbox(
                "默认导出模式",
                ["仅文本翻译", "生成翻译图片", "文本+翻译图片"],
                index=["仅文本翻译", "生成翻译图片", "文本+翻译图片"].index(
                    s.get("translate_default_output_mode", "生成翻译图片")
                ),
            )
            s["translate_text_model"] = PRIMARY_IMAGE_MODEL
            st.text_input(
                "文本链路模型（OCR/文本翻译）",
                MODELS[PRIMARY_IMAGE_MODEL]["name"],
                disabled=True,
                key="admin_translate_text_model_locked",
            )
            s["translate_fast_text_mode"] = st.checkbox(
                "启用极速文本链路（单次OCR+翻译）",
                value=bool(s.get("translate_fast_text_mode", True)),
            )
            s["translate_force_english_output"] = st.checkbox(
                "英文目标启用强制英文校验",
                value=bool(s.get("translate_force_english_output", True)),
            )
            s["translate_english_max_retries"] = st.number_input(
                "翻译英文校验最大重试次数",
                1,
                5,
                int(s.get("translate_english_max_retries", 2)),
            )
            s["translate_cleanup_chinese_overlay"] = st.checkbox(
                "默认清理中文覆盖文案/角标",
                value=bool(s.get("translate_cleanup_chinese_overlay", True)),
            )
            s["translate_bg_max_concurrent"] = st.number_input(
                "后台并发任务上限（同时运行任务数）",
                1,
                6,
                int(s.get("translate_bg_max_concurrent", 2)),
            )
        with t_c3:
            s["translate_default_size_strategy"] = st.selectbox(
                "默认尺寸策略",
                ["保留原比例", "强制1:1", "自定义比例"],
                index=["保留原比例", "强制1:1", "自定义比例"].index(
                    s.get("translate_default_size_strategy", "保留原比例")
                ),
            )
            s["translate_default_ratio"] = st.selectbox(
                "默认目标比例",
                ASPECT_RATIOS,
                index=ASPECT_RATIOS.index(s.get("translate_default_ratio", "1:1")),
            )
            s["translate_default_ratio_method"] = st.selectbox(
                "默认比例处理方式",
                ["居中裁切", "补边(白色)", "补边(边缘取色)"],
                index=["居中裁切", "补边(白色)", "补边(边缘取色)"].index(
                    s.get("translate_default_ratio_method", "补边(白色)")
                ),
            )
            s["translate_default_model"] = PRIMARY_IMAGE_MODEL
            st.text_input(
                "默认翻译模型",
                MODELS[PRIMARY_IMAGE_MODEL]["name"],
                disabled=True,
                key="admin_translate_default_model_locked",
            )
            s["translate_default_resolution"] = "1K"
            st.selectbox(
                "默认翻译出图分辨率",
                ["1K"],
                index=0,
                key="admin_translate_default_resolution_locked",
            )
            s["translate_text_workers"] = st.number_input(
                "文本并发线程数（仅文本模式）",
                min_value=1,
                max_value=6,
                value=int(s.get("translate_text_workers", 2)),
            )
            all_tpls, enabled_tpls = get_translate_compliance_templates()
            tpl_keys = list(enabled_tpls.keys()) if enabled_tpls else ["default"]
            if s.get("translate_default_compliance_template") not in tpl_keys:
                s["translate_default_compliance_template"] = tpl_keys[0]
            s["translate_default_compliance_template"] = st.selectbox(
                "默认合规词模板",
                tpl_keys,
                format_func=lambda x: enabled_tpls.get(x, all_tpls.get(x, {})).get(
                    "name", x
                ),
                index=tpl_keys.index(
                    s.get("translate_default_compliance_template", tpl_keys[0])
                ),
            )
        if st.button(
            "💾 保存翻译默认设置", type="primary", key="save_translate_defaults"
        ):
            save_settings(s)
            st.success("✅ 已保存")

    with tabs[2]:
        st.markdown("### 🔑 API Key管理")
        fixed_keys_env = (os.getenv("SYSTEM_API_KEYS_FIXED") or "").strip()
        if fixed_keys_env:
            sync_mode = (
                (os.getenv("SYSTEM_API_KEYS_SYNC_MODE") or "if_empty").strip().lower()
            )
            st.info(
                f"检测到环境变量 `SYSTEM_API_KEYS_FIXED`，同步模式：`{sync_mode}`。"
            )
        with st.expander("➕ 添加新Key"):
            new_key = st.text_input("API Key", type="password", key="new_key_input")
            new_name = st.text_input("备注", key="new_key_name")
            if st.button("添加", type="primary"):
                if new_key:
                    keys_data = get_api_keys()
                    keys_data["keys"].append(
                        {
                            "key": new_key.strip(),
                            "name": new_name or f"Key-{len(keys_data['keys']) + 1}",
                            "enabled": True,
                        }
                    )
                    save_api_keys(keys_data)
                    st.success("✅ 已添加")
                    st.rerun()

        keys_data = get_api_keys()
        for i, k in enumerate(keys_data.get("keys", [])):
            key_val = k.get("key", "")
            key_display = (
                f"{key_val[:8]}...{key_val[-4:]}" if len(key_val) > 12 else "无效"
            )
            c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1])
            with c1:
                st.text(f"{k.get('name', '')}: {key_display}")
            with c2:
                st.text(k.get("expires", "永久")[:10] if k.get("expires") else "永久")
            with c3:
                keys_data["keys"][i]["enabled"] = st.checkbox(
                    "启用", k.get("enabled", True), key=f"key_en_{i}"
                )
            with c4:
                if st.button("删除", key=f"key_del_{i}"):
                    keys_data["keys"].pop(i)
                    save_api_keys(keys_data)
                    st.rerun()
        if st.button("💾 保存Key设置"):
            save_api_keys(keys_data)
            st.success("✅ 已保存")

    with tabs[3]:
        comp = get_compliance()
        for mode, preset in comp["presets"].items():
            with st.expander(f"{preset['name']}"):
                preset["enabled"] = st.checkbox(
                    "启用", preset.get("enabled", True), key=f"comp_en_{mode}"
                )
                blacklist_str = st.text_area(
                    "黑名单(逗号分隔)",
                    ", ".join(preset.get("blacklist", [])),
                    key=f"comp_bl_{mode}",
                )
                preset["blacklist"] = [
                    w.strip() for w in blacklist_str.split(",") if w.strip()
                ]
        if st.button("💾 保存合规设置", type="primary"):
            save_compliance(comp)
            st.success("✅ 已保存")

        st.markdown("---")
        st.markdown("### 🈯 图片翻译合规词模板")
        templates = comp.get("translate_templates", {})

        with st.expander("➕ 添加模板"):
            new_tpl_id = st.text_input("模板ID (英文)", key="new_tr_tpl_id")
            new_tpl_name = st.text_input("模板名称", key="new_tr_tpl_name")
            new_tpl_words = st.text_area(
                "合规词 (逗号或换行分隔)", height=120, key="new_tr_tpl_words"
            )
            if st.button("添加模板", type="primary", key="add_tr_tpl"):
                if new_tpl_id and new_tpl_name:
                    templates[new_tpl_id] = {
                        "name": new_tpl_name,
                        "words": parse_compliance_words(new_tpl_words),
                        "enabled": True,
                    }
                    comp["translate_templates"] = templates
                    save_compliance(comp)
                    st.success("✅ 已添加")
                    st.rerun()

        for tpl_id, tpl in templates.items():
            with st.expander(f"{tpl.get('name', tpl_id)}"):
                tpl["name"] = st.text_input(
                    "名称", tpl.get("name", ""), key=f"tr_tpl_name_{tpl_id}"
                )
                tpl["enabled"] = st.checkbox(
                    "启用", tpl.get("enabled", True), key=f"tr_tpl_en_{tpl_id}"
                )
                words_text = "\n".join(tpl.get("words", []))
                words_text = st.text_area(
                    "合规词 (逗号或换行分隔)",
                    words_text,
                    height=120,
                    key=f"tr_tpl_words_{tpl_id}",
                )
                tpl["words"] = parse_compliance_words(words_text)
                if tpl_id != "default":
                    if st.button("删除模板", key=f"tr_tpl_del_{tpl_id}"):
                        del templates[tpl_id]
                        comp["translate_templates"] = templates
                        save_compliance(comp)
                        st.rerun()

        if st.button("💾 保存翻译合规模板", type="primary", key="save_tr_tpls"):
            comp["translate_templates"] = templates
            save_compliance(comp)
            st.success("✅ 已保存")

    with tabs[4]:
        prompts = get_prompts()
        prompt_names = {
            "anchor_analysis": "商品分析",
            "requirements_gen": "图需生成",
            "en_copy_gen": "英文文案",
            "image_prompt": "图片生成",
            "size_image_prompt": "尺寸图",
            "image_text_extract": "图片文字提取",
            "image_text_translate": "图片文本翻译",
            "image_text_extract_translate": "图片文字提取+翻译",
            "image_translate_prompt": "图片翻译出图",
        }
        for key, name in prompt_names.items():
            with st.expander(f"📝 {name}"):
                prompts[key] = st.text_area(
                    "内容",
                    prompts.get(key, ""),
                    height=200,
                    key=f"prompt_{key}",
                    label_visibility="collapsed",
                )
                if st.button("恢复默认", key=f"reset_{key}"):
                    prompts[key] = DEFAULT_PROMPTS.get(key, "")
                    st.rerun()
        if st.button("💾 保存提示词", type="primary"):
            save_prompts(prompts)
            st.success("✅ 已保存")

    with tabs[5]:
        title_tpls = get_title_templates()
        st.markdown("### 🏷️ 标题模板管理 (全局生效)")
        st.info("修改后对所有用户生效")

        with st.expander("➕ 添加新模板"):
            new_tpl_id = st.text_input("模板ID (英文)", key="new_tpl_id")
            new_tpl_name = st.text_input("模板名称", key="new_tpl_name")
            new_tpl_desc = st.text_input("描述", key="new_tpl_desc")
            new_tpl_prompt = st.text_area(
                "提示词 ({product_info}为占位符)", height=300, key="new_tpl_prompt"
            )
            if st.button("添加模板", type="primary"):
                if new_tpl_id and new_tpl_name and new_tpl_prompt:
                    title_tpls[new_tpl_id] = {
                        "name": new_tpl_name,
                        "desc": new_tpl_desc,
                        "prompt": new_tpl_prompt,
                        "enabled": True,
                    }
                    save_title_templates(title_tpls)
                    st.success("✅ 已添加")
                    st.rerun()

        for tpl_id, tpl in title_tpls.items():
            with st.expander(f"{tpl.get('name', tpl_id)}"):
                tpl["name"] = st.text_input(
                    "名称", tpl.get("name", ""), key=f"tpl_name_{tpl_id}"
                )
                tpl["desc"] = st.text_input(
                    "描述", tpl.get("desc", ""), key=f"tpl_desc_{tpl_id}"
                )
                tpl["enabled"] = st.checkbox(
                    "启用", tpl.get("enabled", True), key=f"tpl_en_{tpl_id}"
                )
                tpl["prompt"] = st.text_area(
                    "提示词",
                    tpl.get("prompt", ""),
                    height=300,
                    key=f"tpl_prompt_{tpl_id}",
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("恢复默认", key=f"tpl_reset_{tpl_id}"):
                        if tpl_id in DEFAULT_TITLE_TEMPLATES:
                            title_tpls[tpl_id] = DEFAULT_TITLE_TEMPLATES[tpl_id].copy()
                            save_title_templates(title_tpls)
                            st.rerun()
                with c2:
                    if tpl_id not in DEFAULT_TITLE_TEMPLATES:
                        if st.button("删除", key=f"tpl_del_{tpl_id}"):
                            del title_tpls[tpl_id]
                            save_title_templates(title_tpls)
                            st.rerun()
        if st.button("💾 保存标题模板", type="primary"):
            save_title_templates(title_tpls)
            st.success("✅ 已保存 (全局生效)")

    with tabs[6]:
        templates = get_templates()
        st.markdown("### 组图类型")
        for tk, info in templates["combo_types"].items():
            with st.expander(f"{info['icon']} {info['name']}"):
                c1, c2 = st.columns(2)
                with c1:
                    info["name"] = st.text_input(
                        "名称", info["name"], key=f"ct_name_{tk}"
                    )
                    info["icon"] = st.text_input(
                        "图标", info["icon"], key=f"ct_icon_{tk}"
                    )
                    info["enabled"] = st.checkbox(
                        "启用", info.get("enabled", True), key=f"ct_en_{tk}"
                    )
                with c2:
                    info["desc"] = st.text_input(
                        "描述", info["desc"], key=f"ct_desc_{tk}"
                    )
                    info["hint"] = st.text_area(
                        "提示词", info.get("hint", ""), height=80, key=f"ct_hint_{tk}"
                    )
                    info["order"] = st.number_input(
                        "排序", 1, 20, info.get("order", 10), key=f"ct_order_{tk}"
                    )
        if st.button("💾 保存模板", type="primary"):
            save_templates(templates)
            st.success("✅ 已保存")

    with tabs[7]:
        users = get_users()
        if users:
            for uid, u in list(users.items())[:50]:
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                with c1:
                    st.text(f"{uid[:10]}...")
                with c2:
                    st.text(f"总: {u.get('total', 0)}")
                with c3:
                    users[uid]["vip"] = st.checkbox(
                        "VIP", u.get("vip", False), key=f"vip_{uid}"
                    )
                with c4:
                    if st.button("重置", key=f"rst_{uid}"):
                        users[uid]["daily"] = {}
            if st.button("💾 保存用户"):
                save_users(users)
                st.success("✅ 已保存")
        else:
            st.info("暂无用户")

    with tabs[8]:
        st.markdown("### Team Wallet Foundation")
        st.caption(
            "This tab uses the new PostgreSQL billing foundation and is ready for Zeabur managed databases."
        )
        render_billing_admin_tab()

    with tabs[9]:
        st.markdown("### Redeem Code Foundation")
        st.caption(
            "Use batches for admin-issued recharge codes, offline transfer fulfillment, and future channel distribution."
        )
        render_redeem_code_admin_tab()

    st.markdown("---")
    if st.button("← 返回", use_container_width=True):
        st.session_state.show_admin = False
        st.rerun()


# ==================== 主应用 ====================
def main_app():
    with st.sidebar:
        st.markdown(f"### 🍌 {APP_NAME}")
        st.caption(APP_VERSION)
        st.markdown("---")
        page = st.radio(
            "功能",
            ["1 批量出图", "2 快速出图", "3 标题优化", "4 图片翻译"],
            label_visibility="collapsed",
        )
        st.markdown("---")

        if st.session_state.use_own_key:
            st.success("🔑 无限额度")
        else:
            uid = get_user_id()
            _, used, limit = check_user_limit(uid)
            st.info(f"今日: {used}/{limit}")

        if st.session_state.use_own_key or st.session_state.is_admin:
            st.markdown("---")
            with st.expander("🛡️ 自定义合规词"):
                show_user_compliance()
        st.markdown("---")
        render_relay_config_panel("sidebar", get_settings(), expanded=False)

        if st.session_state.is_admin:
            st.markdown("---")
            if st.button("⚙️ 管理后台", use_container_width=True):
                st.session_state.show_admin = True
                st.rerun()

        if st.button("🧹 清理会话缓存", use_container_width=True):
            reset_working_session()
            st.rerun()

        if st.button("🚪 退出", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    if page == "1 批量出图":
        show_combo_page()
    elif page == "2 快速出图":
        show_smart_page()
    elif page == "3 标题优化":
        show_title_page()
    else:
        show_image_translate_page()


# ==================== 主入口 ====================
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} {APP_VERSION}",
        page_icon="🍌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_style()
    init_session()
    bootstrap_runtime_config()
    bootstrap_platform_runtime()
    inject_browser_key_persistence()

    if not st.session_state.authenticated:
        show_login()
        return

    if st.session_state.get("show_admin") and st.session_state.is_admin:
        show_admin()
        return

    main_app()


if __name__ == "__main__":
    main()
