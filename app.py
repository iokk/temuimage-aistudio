"""电商出图工作台.

个人 self-hosted 主线，支持 desktop 与 server 两种运行模式。
"""

import streamlit as st
from PIL import Image
import io
import json
import os
import threading
import re
import hashlib
import base64
import copy
import zipfile
import random
import time
import subprocess
import tempfile
import shutil
import urllib.request
import urllib.error
from datetime import datetime, date
from pathlib import Path
from google import genai
from google.genai import types

# ==================== 配置常量 ====================
APP_VERSION = "V15.2.1"
APP_AUTHOR = "企鹅 & 小明"
APP_COMMERCIAL = "企鹅 & Jerry"
APP_NAME = "电商出图工作台"


def _detect_runtime_mode() -> str:
    runtime = (
        os.getenv("APP_RUNTIME", "")
        or os.getenv("ECOMMERCE_WORKBENCH_MODE", "")
    ).strip().lower()
    if runtime in {"desktop", "server"}:
        return runtime
    if os.path.exists("/app/data"):
        return "server"
    return "desktop"


APP_RUNTIME = _detect_runtime_mode()
DESKTOP_MODE = APP_RUNTIME == "desktop"
SERVER_MODE = APP_RUNTIME == "server"


def runtime_supports_local_file_access() -> bool:
    return DESKTOP_MODE


def runtime_supports_output_dir_editing() -> bool:
    return DESKTOP_MODE


def runtime_label() -> str:
    return "Mac 本地版" if DESKTOP_MODE else "Self-hosted 服务器版"


def _default_data_dir() -> Path:
    env_dir = os.getenv("ECOMMERCE_WORKBENCH_DATA_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return Path("/app/data") if os.path.exists("/app/data") else Path("./data")


def _default_project_output_dir() -> str:
    env_dir = os.getenv("ECOMMERCE_WORKBENCH_PROJECTS_DIR", "").strip()
    if env_dir:
        return str(Path(env_dir).expanduser())
    if SERVER_MODE:
        return str((DATA_DIR / "projects").resolve())
    return str(Path.home() / "Downloads" / APP_NAME)


def _default_file_storage_path() -> str:
    env_dir = os.getenv("FILE_STORAGE_PATH", "").strip()
    if env_dir:
        return str(Path(env_dir).expanduser())
    if os.path.exists("/app/data"):
        return "/app/data/files"
    return str((_default_data_dir() / "files").resolve())


DATA_DIR = _default_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
PROVIDERS_FILE = DATA_DIR / "providers.json"
PROMPTS_FILE = DATA_DIR / "prompts.json"
COMPLIANCE_FILE = DATA_DIR / "compliance.json"
TEMPLATES_FILE = DATA_DIR / "templates.json"
TITLE_TEMPLATES_FILE = DATA_DIR / "title_templates.json"
TASKS_FILE = DATA_DIR / "tasks.json"
HISTORY_FILE = DATA_DIR / "history.json"
HISTORY_DIR = DATA_DIR / "history"

KEYCHAIN_SERVICE = "ecommerce-image-workbench"
MAX_TASK_QUEUE = 5
MAX_ACTIVE_TASKS = 2
TASK_STATUS_TERMINAL = {"done", "error", "cancelled", "expired"}
HISTORY_RECORD_ACTIVE = "active"
HISTORY_RECORD_TRASHED = "trashed"
GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS", "60")
)
GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS", "120")
)

# ==================== 硬性限制 ====================
MAX_IMAGES = 14
MAX_NAME_CHARS = 200
MAX_DETAIL_CHARS = 500
MAX_TAGS = 8
MAX_TYPE_COUNT = 3
MAX_TOTAL_IMAGES = 12
MAX_HEADLINE_CHARS = 40
MAX_SUBLINE_CHARS = 60
MAX_BADGE_CHARS = 20
MAX_RETRIES = 2
MAX_TITLE_INFO_CHARS = 1000

# 标题字符限制
MIN_TITLE_EN_CHARS = 180
MAX_TITLE_EN_CHARS = 250

DEFAULT_TARGET_LANGUAGE = "zh"
TARGET_LANGUAGES = [
    {
        "code": "en",
        "label": "英语",
        "english_name": "English",
        "native_name": "English",
        "flag": "🇺🇸",
        "copy_tag": "EN",
    },
    {
        "code": "zh",
        "label": "中文",
        "english_name": "Chinese",
        "native_name": "中文",
        "flag": "🇨🇳",
        "copy_tag": "ZH",
    },
    {
        "code": "ja",
        "label": "日语",
        "english_name": "Japanese",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "copy_tag": "JA",
    },
    {
        "code": "vi",
        "label": "越南语",
        "english_name": "Vietnamese",
        "native_name": "Tiếng Việt",
        "flag": "🇻🇳",
        "copy_tag": "VI",
    },
    {
        "code": "th",
        "label": "泰语",
        "english_name": "Thai",
        "native_name": "ไทย",
        "flag": "🇹🇭",
        "copy_tag": "TH",
    },
    {
        "code": "fr",
        "label": "法语",
        "english_name": "French",
        "native_name": "Français",
        "flag": "🇫🇷",
        "copy_tag": "FR",
    },
    {
        "code": "es",
        "label": "西班牙语",
        "english_name": "Spanish",
        "native_name": "Español",
        "flag": "🇪🇸",
        "copy_tag": "ES",
    },
]
TARGET_LANGUAGE_MAP = {item["code"]: item for item in TARGET_LANGUAGES}
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

# ==================== Gemini 3 模型配置 ====================
MODELS = {
    "nano-banana": {
        "name": "🍌 Nano Banana",
        "resolutions": ["1K"],
        "max_refs": 3,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
    },
    "gemini-3.1-flash-image-preview": {
        "name": "🍌 Nano Banana 2",
        "resolutions": ["1K"],
        "max_refs": 10,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
    },
    "gemini-3-pro-image-preview": {
        "name": "🍌 Nano Banana Pro",
        "resolutions": ["1K", "2K", "4K"],
        "max_refs": 14,
        "thinking_levels": ["low", "high"],
        "default_thinking": "high",
        "supports_thinking": True,  # 支持thinking_level
    },
    "gemini-2.5-flash-image": {
        "name": "⚡ Nano Banana Flash",
        "resolutions": ["1K"],
        "max_refs": 3,
        "thinking_levels": [],  # 不支持
        "default_thinking": None,
        "supports_thinking": False,  # 不支持thinking_level
    },
}

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

MAIN_NAV_ITEMS = ["🚀 智能组图", "🎨 快速出图 / 图片翻译", "🏷️ 标题生成"]
MANAGEMENT_NAV_ITEMS = ["🧩 模板库", "⚙️ 提供商设置", "🛠️ 系统设置"]
PROJECT_CENTER_PAGE = "📚 项目中心"

# ==================== 默认配置 ====================
DEFAULT_SETTINGS = {
    "default_model": "nano-banana",
    "default_title_model": "gemini-3.1-flash-lite-preview",
    "default_vision_model": "gemini-3.1-flash-lite-preview",
    "default_title_language": "en",
    "default_image_language": "en",
    "project_output_dir": _default_project_output_dir(),
    "proxy_mode": "system",
    "proxy_url": "http://127.0.0.1:10808",
    "default_resolution": "1K",
    "default_aspect": "1:1",
    "default_thinking_level": "high",
    "compliance_mode": "strict",
    "trash_retention_days": 15,
    "file_storage_type": "local",
    "file_retention_days": 7,
    "file_storage_path": _default_file_storage_path(),
    "s3_endpoint": "",
    "s3_bucket": "",
    "s3_region": "",
    "s3_access_key": "",
    "s3_secret_key": "",
    "s3_prefix": "temu-files/",
    "s3_presign_expires": 86400,
}

DEFAULT_PROVIDERS_DATA = {"providers": [], "current_id": ""}
DEFAULT_TASKS_DATA = {"tasks": []}

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
}

# ==================== 标题模板 - 中英双语版 ====================
DEFAULT_TITLE_TEMPLATES = {
    "default": {
        "name": "🎯 TEMU标准优化 (英文 + 目标语言)",
        "desc": "完整规则，生成英文 + 目标语言标题，英文180-250字符",
        "prompt": """ROLE You are an ecommerce title optimization expert for TEMU and similar marketplace search systems. Your job is to generate high exposure high clarity English product titles based ONLY on the product information I provide. Never invent features materials sizes certifications compatibility or quantities that are not explicitly given or clearly visible.

INPUT I will provide one of the following A Product text description and attributes B One image or multiple images C A mix of text and images

TASK Generate exactly three product titles for the same product. Each title must have BOTH English and {target_language_name} versions. Each title must be different in keyword focus and conversion angle while staying truthful.

HARD OUTPUT RULES
1 Each title must have TWO lines: first line English, second line {target_language_name} translation
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
{target_language_name} translation must be accurate and natural

OUTPUT FORMAT (exactly 6 lines, no labels):
[English Title 1 - 180-250 chars]
[{target_language_name} Title 1]
[English Title 2 - 180-250 chars]
[{target_language_name} Title 2]
[English Title 3 - 180-250 chars]
[{target_language_name} Title 3]

Product information:
{product_info}

NOW GENERATE the six lines.""",
        "enabled": True,
    },
    "simple": {
        "name": "⚡ 简洁高效 (英文 + 目标语言)",
        "desc": "快速生成英文 + 目标语言标题",
        "prompt": """Generate 3 product titles for TEMU marketplace. Each title needs English and {target_language_name} versions.

Product: {product_info}

Rules:
- English: 180-250 characters, plain text, letters numbers spaces only
- {target_language_name}: accurate translation
- No symbols, no brand names unless provided
- No meaningless words like Best Cheap Hot
- Title Case capitalization

Output exactly 6 lines (English then {target_language_name} for each):
[English Title 1]
[{target_language_name} Title 1]
[English Title 2]
[{target_language_name} Title 2]
[English Title 3]
[{target_language_name} Title 3]""",
        "enabled": True,
    },
    "detailed": {
        "name": "📝 详细规格 (英文 + 目标语言)",
        "desc": "适合规格复杂的商品",
        "prompt": """You are a TEMU title expert. Create 3 bilingual titles in English and {target_language_name}.

Product details:
{product_info}

Requirements:
- English: 180-250 characters, plain text
- {target_language_name}: natural translation
- Include specifications if provided
- No invented features
- Title Case capitalization

Focus areas:
Title 1: Category keyword + specs (搜索优化)
Title 2: Benefits + use case (转化优化)
Title 3: Unique features + target user (差异化)

Output exactly 6 lines:
[English Title 1]
[{target_language_name} Title 1]
[English Title 2]
[{target_language_name} Title 2]
[English Title 3]
[{target_language_name} Title 3]""",
        "enabled": True,
    },
    "image_analysis": {
        "name": "🖼️ 图片智能分析 (英文 + 目标语言)",
        "desc": "根据商品图片AI分析生成英文 + 目标语言标题",
        "prompt": """Analyze the product image(s) and generate 3 bilingual titles for TEMU marketplace in English and {target_language_name}.

Additional info: {product_info}

Based on what you see in the image:
1. Identify product category and type
2. Note visible features, materials, colors, design
3. Consider target customer and use cases

RULES:
- English: 180-250 characters, plain text, letters numbers spaces only
- {target_language_name}: accurate natural translation
- Do NOT invent features not visible
- Do NOT include brand names unless clearly visible
- Title Case capitalization

Output exactly 6 lines:
[English Title 1]
[{target_language_name} Title 1]
[English Title 2]
[{target_language_name} Title 2]
[English Title 3]
[{target_language_name} Title 3]""",
        "enabled": True,
    },
}

DEFAULT_PROMPTS = {
    "anchor_analysis": """Analyze these product images and return JSON:
{"primary_category": "category", "product_name_en": "English name", "product_name_zh": "中文名", "visual_attrs": ["attr1", "attr2"], "confidence": 0.8}
Product name: {product_name}
Product detail: {product_detail}
Return valid JSON only. ALL text in English.""",
    "requirements_gen": """You are an ecommerce image-planning expert. Generate product image requirements in {output_language_name}.
Product: {product_name} ({category})
Features: {features}
Tags: {tags}
Requested image types: {types}
Return a JSON array:
[{{"type_key": "xxx", "type_name": "type name in {output_language_name}", "index": 1, "topic": "topic within 30 chars in {output_language_name}", "scene": "scene within 80 chars in {output_language_name}", "copy": "copy within 50 chars in {output_language_name}"}}]
Rules: write type_name topic scene and copy in {output_language_name}. Do not invent missing facts. Avoid certifications medical claims and absolutes. For size diagrams, keep unit labels as inch and cm. Return valid JSON only.""",
    "en_copy_gen": """Generate product image copy in {output_language_name}.
Product: {product_name}
Category: {category}
Requirements: {requirements}
Generate JSON array:
[{{"type_key": "xxx", "index": 1, "headline": "max 40 chars", "subline": "max 60 chars", "badge": "max 20 chars or empty"}}]
CRITICAL: Use concise natural {output_language_name} only. Keep each field short and readable for ecommerce images. Return valid JSON.""",
    "image_prompt": """Professional ecommerce product image.
Product: {product_name}
Category: {category}
Image type: {image_type}
Style: {style_hint}
Scene: {scene}
Text overlay ({output_language_name} ONLY):
{text_content}
CRITICAL: Product must match reference. If the image contains text, use {output_language_name} only. Professional ecommerce style.
Aspect ratio: {aspect_ratio}""",
    "size_image_prompt": """Professional product dimension diagram.
Product: {product_name}
Style: Clean technical illustration on white background
REQUIRED: Clear bidirectional arrow lines. Dual unit measurements: XX.XX inch / XX.X cm. Use word "inch" NOT "in". Clean sans-serif font. Use {output_language_name} for descriptive labels and notes while keeping inch and cm for units.
Aspect ratio: {aspect_ratio}""",
    "translation_image_prompt": """Translate this ecommerce image into {output_language_name} while preserving the original layout as much as possible.
Goal: compliance-first translation, not creative redesign.
Rules:
- Keep product, composition, visual hierarchy, icon positions and structure as close to the original as possible.
- Replace only visible text and compliance-risk words when needed.
- Do not add new selling claims, badges, certifications or decorations.
- If any source text is unclear, use the safest neutral wording.
- The final image text must use {output_language_name} only.
- Respect these compliance constraints:
{compliance_rules}
Aspect ratio: {aspect_ratio}""",
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
            "name": "功能卖点图",
            "icon": "⭐",
            "desc": "突出商品核心卖点与优势的说明图",
            "hint": "Feature highlights with callouts",
            "enabled": True,
            "order": 2,
        },
        "scene": {
            "name": "场景应用图",
            "icon": "🏠",
            "desc": "展示商品在真实使用场景中的效果",
            "hint": "Lifestyle scene, product in use",
            "enabled": True,
            "order": 3,
        },
        "detail": {
            "name": "细节特写图",
            "icon": "🔍",
            "desc": "放大展示材质、工艺和细节做工",
            "hint": "Macro close-up shot, texture details",
            "enabled": True,
            "order": 4,
        },
        "size": {
            "name": "尺寸规格图",
            "icon": "📐",
            "desc": "展示尺寸、规格或参数信息的说明图",
            "hint": "Dimension diagram with inch/cm",
            "enabled": True,
            "order": 5,
            "special": True,
        },
        "compare": {
            "name": "对比优势图",
            "icon": "⚖️",
            "desc": "用对比方式突出商品优势与差异点",
            "hint": "Side by side comparison",
            "enabled": True,
            "order": 6,
        },
        "package": {
            "name": "包装清单图",
            "icon": "📦",
            "desc": "展示包装内包含的商品与配件内容",
            "hint": "Flat lay of package contents",
            "enabled": True,
            "order": 7,
        },
        "steps": {
            "name": "操作引导图",
            "icon": "📋",
            "desc": "用于说明安装、使用流程或操作顺序的信息图",
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
    "translation_types": {
        "preserve_layout": {
            "name": "原图保版翻译",
            "icon": "🈯",
            "desc": "尽量保留原图结构、排版和视觉层级，只替换目标语言文案。",
            "enabled": True,
            "order": 1,
            "prompt": DEFAULT_PROMPTS["translation_image_prompt"],
        },
        "compliance_replace": {
            "name": "合规替换翻译",
            "icon": "🛡️",
            "desc": "在翻译时同步替换高风险表达，优先满足合规要求。",
            "enabled": True,
            "order": 2,
            "prompt": DEFAULT_PROMPTS["translation_image_prompt"]
            + "\nExtra rule: When the source contains risky claims or compliance-sensitive wording, replace them with safer alternatives instead of direct literal translation.",
        },
        "minimal_change": {
            "name": "文案最小变更翻译",
            "icon": "✂️",
            "desc": "尽量少改原图内容，只处理必要的文字替换和风险修正。",
            "enabled": True,
            "order": 3,
            "prompt": DEFAULT_PROMPTS["translation_image_prompt"]
            + "\nExtra rule: Keep all non-essential wording changes to a minimum and avoid rewriting visual structure or emphasis unless required for compliance.",
        },
    },
}

TEMPLATE_PAGE_META = {
    "combo_types": {
        "title": "智能组图模板",
        "desc": "用于“智能组图”页面中的可选组图类型，决定系统会生成哪些图片结构。",
        "page_label": "智能组图",
    },
    "smart_types": {
        "title": "快速出图模板",
        "desc": "用于“快速出图”页面中的快捷模板选择，适合快速生成卖点图、场景图、细节图等标准类型。",
        "page_label": "快速出图",
    },
    "translation_types": {
        "title": "翻译保版模板",
        "desc": "用于“快速出图 > 合规翻译”模式，控制原图保留程度与文案替换策略。",
        "page_label": "快速出图（翻译保版）",
    },
}

TEMPLATE_ITEM_META = {
    "combo_types": {
        "main": {
            "recommended_name": "主图白底",
            "recommended_desc": "用于生成标准白底主图，突出商品主体，适合作为主展示图。",
            "usage_note": "适合首页主图、白底展示、商品主体突出场景。",
        },
        "feature": {
            "recommended_name": "功能卖点图",
            "recommended_desc": "用于集中展示商品的核心优势、功能亮点或主打卖点。",
            "usage_note": "适合强调功能亮点、优势对比、核心卖点说明。",
        },
        "scene": {
            "recommended_name": "场景应用图",
            "recommended_desc": "用于呈现商品在真实场景中的使用方式和氛围。",
            "usage_note": "适合家居、户外、办公、日常使用等场景化表达。",
        },
        "detail": {
            "recommended_name": "细节特写图",
            "recommended_desc": "用于放大展示材质、纹理、结构、做工等细节信息。",
            "usage_note": "适合近景细节、质感说明、工艺展示。",
        },
        "size": {
            "recommended_name": "尺寸规格图",
            "recommended_desc": "用于说明尺寸、规格、容量、参数等信息。",
            "usage_note": "适合需要标注尺寸、单位和参数说明的商品。",
        },
        "compare": {
            "recommended_name": "对比优势图",
            "recommended_desc": "用于通过对比方式突出商品优点与差异。",
            "usage_note": "适合和竞品、旧款或不同方案做对比展示。",
        },
        "package": {
            "recommended_name": "包装清单图",
            "recommended_desc": "用于展示包装内包含的主体商品、配件和清单。",
            "usage_note": "适合套装、组合商品、带配件商品。",
        },
        "steps": {
            "recommended_name": "操作引导图",
            "recommended_desc": "用于说明安装流程、操作顺序或使用步骤。",
            "usage_note": "适合需要分步骤教学、安装说明、使用引导的商品。",
        },
    },
    "smart_types": {
        "S1": {
            "recommended_name": "卖点图",
            "recommended_desc": "用于快速突出商品核心优势，适合标准卖点表达。",
            "usage_note": "适合快速出图中的单卖点强化展示。",
        },
        "S2": {
            "recommended_name": "场景图",
            "recommended_desc": "用于快速展示商品在场景中的呈现效果。",
            "usage_note": "适合快速生成带氛围感的场景图。",
        },
        "S3": {
            "recommended_name": "细节图",
            "recommended_desc": "用于快速突出商品局部细节和工艺表现。",
            "usage_note": "适合强调材质、纹理、结构亮点。",
        },
        "S4": {
            "recommended_name": "对比图",
            "recommended_desc": "用于快速通过对比方式体现差异和优势。",
            "usage_note": "适合有限篇幅下的优劣对比表达。",
        },
        "S5": {
            "recommended_name": "规格图",
            "recommended_desc": "用于快速展示尺寸、参数或规格信息。",
            "usage_note": "适合尺寸参数明确、信息说明型图片。",
        },
    },
    "translation_types": {
        "preserve_layout": {
            "recommended_name": "原图保版翻译",
            "recommended_desc": "尽量保留原图结构、排版和视觉层级，只替换目标语言文案。",
            "usage_note": "适合对原图布局要求高的标准保版翻译任务。",
        },
        "compliance_replace": {
            "recommended_name": "合规替换翻译",
            "recommended_desc": "在翻译时同步替换高风险表达，优先满足合规要求。",
            "usage_note": "适合平台规则严格、需要主动替换风险词的场景。",
        },
        "minimal_change": {
            "recommended_name": "文案最小变更翻译",
            "recommended_desc": "尽量少改原图内容，只处理必要的文字替换和风险修正。",
            "usage_note": "适合尽量维持原图表达，只做必要翻译修改的场景。",
        },
    },
}

TEMPLATE_GROUP_ORDER = ["combo_types", "smart_types", "translation_types"]


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


def get_settings():
    s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    for k, v in DEFAULT_SETTINGS.items():
        if k not in s:
            s[k] = v
    return s


def save_settings(s):
    return save_json(SETTINGS_FILE, s)


def apply_proxy_settings(settings=None):
    s = settings or get_settings()
    mode = (s.get("proxy_mode") or "system").strip().lower()
    proxy_url = (s.get("proxy_url") or "").strip()
    if mode == "none":
        for key in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ]:
            os.environ.pop(key, None)
        return "none", ""
    if mode == "manual" and proxy_url:
        for key in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ]:
            os.environ[key] = proxy_url
        return "manual", proxy_url
    return "system", proxy_url


def keychain_available():
    return DESKTOP_MODE and os.name == "posix" and Path("/usr/bin/security").exists()


def _keychain_account(provider_id: str) -> str:
    return f"provider-{provider_id}"


def set_keychain_secret(account: str, secret: str) -> tuple:
    if not keychain_available() or not secret:
        return False, "keychain_unavailable"
    try:
        subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-U",
                "-a",
                account,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
                secret,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or e.stdout or str(e)).strip()


def get_keychain_secret(account: str) -> str:
    if not keychain_available() or not account:
        return ""
    try:
        proc = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                account,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return (proc.stdout or "").strip()
    except subprocess.CalledProcessError:
        return ""


def delete_keychain_secret(account: str):
    if not keychain_available() or not account:
        return
    try:
        subprocess.run(
            [
                "/usr/bin/security",
                "delete-generic-password",
                "-a",
                account,
                "-s",
                KEYCHAIN_SERVICE,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return


def _new_provider_id():
    return hashlib.md5(
        f"{datetime.now().timestamp()}{random.random()}".encode()
    ).hexdigest()[:10]


def _normalize_provider_entry(entry):
    if not isinstance(entry, dict):
        return None
    pid = (entry.get("id") or "").strip() or _new_provider_id()
    name = (entry.get("name") or "").strip() or "个人提供商"
    provider_type = (entry.get("provider_type") or "gemini").strip().lower()
    api_key = (entry.get("api_key") or "").strip()
    base_url = (entry.get("base_url") or "").strip()
    title_model = (entry.get("title_model") or "").strip()
    vision_model = (entry.get("vision_model") or "").strip()
    image_model = (entry.get("image_model") or "").strip()
    enabled = bool(entry.get("enabled", True))
    is_default = bool(entry.get("is_default", False))
    secret_storage = (entry.get("secret_storage") or "plain").strip().lower()
    keychain_account = (
        entry.get("keychain_account") or ""
    ).strip() or _keychain_account(pid)
    return {
        "id": pid,
        "name": name,
        "provider_type": provider_type,
        "api_key": api_key,
        "base_url": base_url,
        "title_model": title_model,
        "vision_model": vision_model,
        "image_model": image_model,
        "enabled": enabled,
        "is_default": is_default,
        "secret_storage": secret_storage,
        "keychain_account": keychain_account,
    }


def _normalize_providers_data(data):
    if data is None:
        data = DEFAULT_PROVIDERS_DATA.copy()
    if isinstance(data, list):
        data = {"providers": data, "current_id": ""}
    if not isinstance(data, dict):
        data = DEFAULT_PROVIDERS_DATA.copy()
    providers = data.get("providers", [])
    if not isinstance(providers, list):
        providers = []
    cleaned = []
    seen_ids = set()
    for p in providers:
        normalized = _normalize_provider_entry(p)
        if not normalized:
            continue
        if normalized["id"] in seen_ids:
            normalized["id"] = _new_provider_id()
        seen_ids.add(normalized["id"])
        cleaned.append(normalized)
    data["providers"] = cleaned
    current_id = (data.get("current_id") or "").strip()
    data["current_id"] = current_id
    return data


def save_providers(data):
    return save_json(PROVIDERS_FILE, data)


def resolve_provider_api_key(provider: dict) -> str:
    if not provider:
        return ""
    if provider.get("secret_storage") == "keychain":
        return get_keychain_secret(provider.get("keychain_account"))
    return (provider.get("api_key") or "").strip()


def persist_provider_secret(provider: dict, api_key: str):
    api_key = (api_key or "").strip()
    if not provider:
        return provider, False
    if keychain_available() and api_key:
        ok, _ = set_keychain_secret(
            provider.get("keychain_account")
            or _keychain_account(provider.get("id", "")),
            api_key,
        )
        if ok:
            provider["secret_storage"] = "keychain"
            provider["keychain_account"] = provider.get(
                "keychain_account"
            ) or _keychain_account(provider.get("id", ""))
            provider["api_key"] = ""
            return provider, True
    provider["secret_storage"] = "plain"
    provider["api_key"] = api_key
    return provider, False


def migrate_provider_secrets(data):
    changed = False
    for provider in data.get("providers", []):
        raw_key = (provider.get("api_key") or "").strip()
        if (
            raw_key
            and provider.get("secret_storage") != "keychain"
            and keychain_available()
        ):
            provider, moved = persist_provider_secret(provider, raw_key)
            changed = changed or moved
    if changed:
        save_providers(data)
    return data


def _bootstrap_env_provider(data):
    s = get_settings()
    env_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not env_key:
        return data
    if data.get("providers"):
        return data
    provider = {
        "id": _new_provider_id(),
        "name": "环境变量Key",
        "provider_type": "gemini",
        "api_key": env_key,
        "base_url": "",
        "title_model": s.get("default_title_model", "gemini-3.1-flash-lite-preview"),
        "vision_model": s.get("default_vision_model", "gemini-3.1-flash-lite-preview"),
        "image_model": s.get("default_model", "gemini-3.1-flash-image-preview"),
        "enabled": True,
        "is_default": True,
    }
    data["providers"] = [provider]
    data["current_id"] = provider["id"]
    return data


def get_providers():
    data = load_json(PROVIDERS_FILE, DEFAULT_PROVIDERS_DATA)
    data = _normalize_providers_data(data)
    if not data.get("providers"):
        data = _bootstrap_env_provider(data)
    data = migrate_provider_secrets(data)
    save_providers(data)
    return data


def get_active_provider():
    data = get_providers()
    providers = [p for p in data.get("providers", []) if p.get("enabled", True)]
    current_id = (data.get("current_id") or "").strip()
    current = next((p for p in providers if p.get("id") == current_id), None)
    if not current and providers:
        current = next((p for p in providers if p.get("is_default")), None)
        current = current or providers[0]
        data["current_id"] = current.get("id")
        for p in data.get("providers", []):
            p["is_default"] = p.get("id") == current.get("id")
        save_providers(data)
    if current:
        current = current.copy()
        current["api_key"] = resolve_provider_api_key(current)
    return current


def set_current_provider(provider_id: str):
    data = get_providers()
    providers = data.get("providers", [])
    for p in providers:
        p["is_default"] = p.get("id") == provider_id
    data["current_id"] = provider_id
    save_providers(data)


def get_provider_by_id(provider_id: str):
    data = get_providers()
    provider = next(
        (p for p in data.get("providers", []) if p.get("id") == provider_id), None
    )
    if provider:
        provider = provider.copy()
        provider["api_key"] = resolve_provider_api_key(provider)
    return provider


def validate_provider_config(
    name: str,
    provider_type: str,
    api_key: str,
    base_url: str,
):
    errors = []
    if not (name or "").strip():
        errors.append("请填写提供商名称。")
    if not (api_key or "").strip():
        errors.append("请填写 API Key。")
    normalized_type = (provider_type or "gemini").strip().lower()
    normalized_base = (base_url or "").strip()
    if normalized_type == "relay" and not normalized_base:
        errors.append("Relay 类型必须填写 Base URL。")
    if normalized_base and not re.match(r"^https?://", normalized_base):
        errors.append("Base URL 必须以 http:// 或 https:// 开头。")
    return errors


def provider_has_active_tasks(provider_id: str):
    if not provider_id:
        return False
    for task in list_tasks():
        if task.get("status") not in {"queued", "running"}:
            continue
        payload = task.get("payload", {}) or {}
        if payload.get("provider_id") == provider_id:
            return True
    return False


def find_replacement_provider(excluded_provider_id: str = ""):
    data = get_providers()
    providers = data.get("providers", [])
    enabled = [
        p
        for p in providers
        if p.get("id") != excluded_provider_id and p.get("enabled", True)
    ]
    return enabled[0] if enabled else None


TASK_LOCK = threading.Lock()
TASK_THREADS = {}


def _new_task_id():
    return hashlib.md5(
        f"task-{datetime.now().timestamp()}-{random.random()}".encode()
    ).hexdigest()[:12]


@st.cache_resource(show_spinner=False)
def get_task_runtime():
    try:
        TASKS_FILE.unlink()
    except (FileNotFoundError, OSError):
        pass
    return {"tasks": [], "threads": {}}


def get_task_store():
    runtime = get_task_runtime()
    tasks = runtime.get("tasks")
    if not isinstance(tasks, list):
        runtime["tasks"] = []
    return runtime


def get_task_threads():
    runtime = get_task_runtime()
    threads = runtime.get("threads")
    if not isinstance(threads, dict):
        runtime["threads"] = {}
    return runtime["threads"]


def get_tasks_data():
    data = get_task_store()
    if not isinstance(data, dict):
        data = {"tasks": []}
    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    data["tasks"] = tasks
    return data


def save_tasks_data(data):
    store = get_task_store()
    store["tasks"] = data.get("tasks", []) if isinstance(data, dict) else []
    return store


def get_history_data():
    data = load_json(HISTORY_FILE, {"records": []})
    if not isinstance(data, dict):
        data = {"records": []}
    records = data.get("records", [])
    if not isinstance(records, list):
        records = []
    data["records"] = [_normalize_history_record(record) for record in records]
    return data


def save_history_data(data):
    return save_json(HISTORY_FILE, data)


def _normalize_history_record(record: dict):
    normalized = copy.deepcopy(record or {})
    state = (normalized.get("record_state") or "").strip().lower()
    if state not in {HISTORY_RECORD_ACTIVE, HISTORY_RECORD_TRASHED}:
        state = HISTORY_RECORD_ACTIVE
    normalized["record_state"] = state
    normalized["trashed_at"] = (normalized.get("trashed_at") or "").strip()
    normalized["purged_at"] = (normalized.get("purged_at") or "").strip()
    return normalized


def _history_sort_key(record: dict):
    return record.get("completed_at", record.get("created_at", ""))


def list_history_records(record_states=None):
    data = get_history_data()
    records = [_normalize_history_record(r) for r in data.get("records", [])]
    if record_states:
        allowed_states = {
            str(state or "").strip().lower() for state in record_states if state
        }
        records = [r for r in records if r.get("record_state") in allowed_states]
    return sorted(records, key=_history_sort_key, reverse=True)


def list_active_history_records():
    return list_history_records({HISTORY_RECORD_ACTIVE})


def list_trashed_history_records():
    return list_history_records({HISTORY_RECORD_TRASHED})


def get_project_output_base_dir():
    s = get_settings()
    base = (s.get("project_output_dir") or _default_project_output_dir()).strip()
    path = Path(base).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify_project_name(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", (text or "未命名项目").strip())
    cleaned = cleaned.strip("_")
    return cleaned[:60] or "未命名项目"


def _task_datetime(task: dict) -> datetime:
    raw = (task or {}).get("created_at") or datetime.now().isoformat()
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return datetime.now()


def _parse_iso_datetime(raw: str):
    try:
        return datetime.fromisoformat((raw or "").strip())
    except Exception:
        return None


def _project_folder_name(task: dict) -> str:
    created_at = _task_datetime(task).strftime("%Y%m%d_%H%M%S")
    label = _slugify_project_name(task.get("summary") or task.get("type") or "项目")
    return f"{created_at}_{label}_{(task.get('id') or _new_task_id())[:6]}"


def _history_record_dir(task: dict, existing_record: dict = None):
    if existing_record and existing_record.get("artifact_dir"):
        return Path(existing_record.get("artifact_dir"))
    return get_project_output_base_dir() / _project_folder_name(task)


def iter_project_manifest_paths():
    base_dir = get_project_output_base_dir()
    if not base_dir.exists():
        return []
    return sorted(base_dir.glob("*/manifest.json"))


def load_manifest_record(manifest_path: Path):
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("artifact_dir"):
        data["artifact_dir"] = str(manifest_path.parent)
    if not data.get("project_name"):
        data["project_name"] = manifest_path.parent.name
    return _normalize_history_record(data)


def write_manifest_record(record: dict):
    artifact_dir = Path((record or {}).get("artifact_dir", ""))
    if not artifact_dir:
        return False
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = artifact_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except Exception:
        return False


def replace_history_record(task_id: str, updated_record: dict):
    data = get_history_data()
    replaced = False
    records = []
    for record in data.get("records", []):
        if record.get("task_id") == task_id:
            records.append(_normalize_history_record(updated_record))
            replaced = True
        else:
            records.append(record)
    if not replaced:
        return None
    data["records"] = records
    save_history_data(data)
    write_manifest_record(_normalize_history_record(updated_record))
    return _normalize_history_record(updated_record)


def get_history_record(task_id: str):
    return next(
        (record for record in list_history_records() if record.get("task_id") == task_id),
        None,
    )


def rebuild_history_index_from_manifests():
    existing_records = {
        record.get("task_id"): record for record in get_history_data().get("records", [])
    }
    rebuilt_records = []
    for manifest_path in iter_project_manifest_paths():
        record = load_manifest_record(manifest_path)
        if not record or not record.get("task_id"):
            continue
        existing = existing_records.get(record.get("task_id"), {})
        if existing:
            record["record_state"] = existing.get(
                "record_state", record.get("record_state", HISTORY_RECORD_ACTIVE)
            )
            if record["record_state"] == HISTORY_RECORD_TRASHED:
                record["trashed_at"] = existing.get("trashed_at", record.get("trashed_at", ""))
        rebuilt_records.append(record)
    save_history_data({"records": rebuilt_records})
    return rebuilt_records


def find_orphan_project_dirs(records: list):
    base_dir = get_project_output_base_dir()
    if not base_dir.exists():
        return []
    tracked_dirs = {
        str(Path(record.get("artifact_dir")).resolve())
        for record in records
        if record.get("artifact_dir")
    }
    orphan_dirs = []
    for child in sorted(base_dir.iterdir()):
        if not child.is_dir():
            continue
        child_resolved = str(child.resolve())
        has_manifest = (child / "manifest.json").exists()
        if child_resolved in tracked_dirs:
            continue
        # Keep directories with content visible to the user so they can repair or inspect them.
        file_count = sum(1 for item in child.rglob("*") if item.is_file())
        if has_manifest or file_count > 0:
            orphan_dirs.append(
                {
                    "path": str(child),
                    "name": child.name,
                    "has_manifest": has_manifest,
                    "size_bytes": get_path_size(child),
                    "file_count": file_count,
                }
            )
    return orphan_dirs


def cleanup_expired_trashed_records():
    settings = get_settings()
    retention_days = int(settings.get("trash_retention_days", 15) or 0)
    if retention_days <= 0:
        return []
    now = datetime.now()
    data = get_history_data()
    removable_task_ids = []
    for record in data.get("records", []):
        if record.get("record_state") != HISTORY_RECORD_TRASHED:
            continue
        trashed_at = _parse_iso_datetime(record.get("trashed_at"))
        if not trashed_at:
            continue
        if (now - trashed_at).days >= retention_days:
            removable_task_ids.append(record.get("task_id"))
    purged_records = []
    for task_id in removable_task_ids:
        purged = purge_trashed_history_record(task_id)
        if purged:
            purged_records.append(purged)
    return purged_records


def rebuild_record_zip(task_id: str):
    record = get_history_record(task_id)
    if not record:
        return None, "未找到项目记录。"
    artifact_dir = Path(record.get("artifact_dir", ""))
    if not artifact_dir.exists():
        return None, "项目目录不存在，无法重建 ZIP。"
    zip_path = _write_history_zip(
        artifact_dir,
        record.get("file_paths", []) or [],
        record.get("titles", []) or [],
        record.get("target_language", DEFAULT_TARGET_LANGUAGE),
        errors=record.get("errors", []) or [],
    )
    updated_record = copy.deepcopy(record)
    updated_record["zip_path"] = zip_path
    updated_record["updated_at"] = datetime.now().isoformat()
    replace_history_record(task_id, updated_record)
    return _normalize_history_record(updated_record), ""


def delete_orphan_project_dir(path_str: str):
    if not path_str:
        return False
    target = Path(path_str)
    if not target.exists() or not target.is_dir():
        return False
    try:
        shutil.rmtree(target, ignore_errors=True)
        return True
    except Exception:
        return False


def restore_all_trashed_history_records():
    restored = []
    for record in list_trashed_history_records():
        restored_record = restore_history_record(record.get("task_id"))
        if restored_record:
            restored.append(restored_record)
    return restored


def trash_history_records_by_ids(task_ids):
    moved = []
    for task_id in task_ids or []:
        moved_record = trash_history_record(task_id)
        if moved_record:
            moved.append(moved_record)
    return moved


def restore_history_records_by_ids(task_ids):
    restored = []
    for task_id in task_ids or []:
        restored_record = restore_history_record(task_id)
        if restored_record:
            restored.append(restored_record)
    return restored


def purge_trashed_history_records_by_ids(task_ids):
    purged = []
    for task_id in task_ids or []:
        purged_record = purge_trashed_history_record(task_id)
        if purged_record:
            purged.append(purged_record)
    return purged


def _safe_copy_to_dir(src: str, dest_dir: Path, dest_name: str = ""):
    if not src:
        return None
    src_path = Path(src)
    if not src_path.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / (dest_name or src_path.name)
    shutil.copy2(src_path, target)
    return str(target)


def _write_history_zip(
    dest_dir: Path,
    file_paths: list,
    titles: list,
    target_language: str,
    errors: list = None,
):
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "download.zip"
    language_info = get_target_language(target_language)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in file_paths or []:
            if not path:
                continue
            src = Path(path)
            if src.exists():
                z.write(src, arcname=src.name)
        if titles:
            if target_language == "en":
                titles_content = "\n\n".join(
                    [f"Title {i + 1}:\nEN: {t}" for i, t in enumerate(titles)]
                )
            else:
                titles_content = "\n\n".join(
                    [
                        f"标题 {i // 2 + 1}:\nEN: {titles[i]}\n{language_info['copy_tag']}: {titles[i + 1]}"
                        for i in range(0, len(titles) - 1, 2)
                    ]
                )
            if not titles_content and titles:
                titles_content = "\n".join(
                    [f"Title {i + 1}: {t}" for i, t in enumerate(titles)]
                )
            z.writestr("titles.txt", titles_content)
        if errors:
            z.writestr("errors.txt", "\n".join([str(err) for err in errors if err]))
    return str(zip_path)


def _write_project_text_files(
    dest_dir: Path, titles: list, errors: list, target_language: str
):
    dest_dir.mkdir(parents=True, exist_ok=True)
    if titles:
        language_info = get_target_language(target_language)
        if target_language == "en":
            content = "\n\n".join(
                [f"Title {i + 1}:\nEN: {t}" for i, t in enumerate(titles)]
            )
        else:
            content = "\n\n".join(
                [
                    f"标题 {i // 2 + 1}:\nEN: {titles[i]}\n{language_info['copy_tag']}: {titles[i + 1]}"
                    for i in range(0, len(titles) - 1, 2)
                ]
            )
        (dest_dir / "titles.txt").write_text(content or "", encoding="utf-8")
    if errors:
        (dest_dir / "errors.txt").write_text(
            "\n".join([str(err) for err in errors if err]), encoding="utf-8"
        )


def _copy_input_files_for_history(task: dict, artifact_dir: Path):
    payload = copy.deepcopy((task or {}).get("payload", {}) or {})
    input_paths = payload.get("image_paths", []) or []
    copied_inputs = []
    if input_paths:
        input_dir = artifact_dir / "inputs"
        for idx, src in enumerate(input_paths):
            src_path = Path(src)
            suffix = src_path.suffix or ".png"
            copied = _safe_copy_to_dir(src, input_dir, f"input_{idx + 1:02d}{suffix}")
            if copied:
                copied_inputs.append(copied)
        payload["image_paths"] = copied_inputs
    return payload, copied_inputs


def _normalize_relaunch_summary(summary: str) -> str:
    base = re.sub(r"^重发\s*·\s*", "", (summary or "未命名项目")).strip()
    return f"重发 · {base}"


def build_relaunch_payload(record: dict):
    payload = copy.deepcopy((record or {}).get("payload", {}) or {})
    if payload:
        payload["summary"] = _normalize_relaunch_summary(
            payload.get("summary") or record.get("summary", "")
        )
        if payload.get("provider_id") and not get_provider_by_id(
            payload.get("provider_id")
        ):
            active = get_active_provider() or {}
            if active.get("id"):
                payload["provider_id"] = active.get("id")
        return payload
    return {}


def relaunch_history_record(task_id: str):
    record = next(
        (r for r in list_history_records() if r.get("task_id") == task_id), None
    )
    if not record:
        return None, "未找到项目记录"
    payload = build_relaunch_payload(record)
    if not payload:
        return None, "该历史项目缺少可重发参数，请先重新生成一次新项目。"
    task, err = create_task(record.get("task_type", "task"), payload)
    if task:
        schedule_task_workers()
    return task, err


def record_task_history(task: dict, result: dict):
    if not task or task.get("status") not in TASK_STATUS_TERMINAL:
        return None
    task_id = task.get("id") or _new_task_id()
    data = get_history_data()
    existing_record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    artifact_dir = _history_record_dir(task, existing_record)
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir, ignore_errors=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    file_sources = result.get("files", []) or task.get("result_files", []) or []
    copied_files = []
    for idx, src in enumerate(file_sources):
        copied = _safe_copy_to_dir(src, artifact_dir, f"{idx + 1:02d}_{Path(src).name}")
        if copied:
            copied_files.append(copied)

    titles = result.get("titles", []) or task.get("titles", []) or []
    errors = result.get("errors", []) or task.get("errors", []) or []
    target_language = (
        result.get("target_language")
        or task.get("result_title_language")
        or DEFAULT_TARGET_LANGUAGE
    )
    payload_snapshot, copied_input_paths = _copy_input_files_for_history(
        task, artifact_dir
    )
    _write_project_text_files(artifact_dir, titles, errors, target_language)
    zip_path = _write_history_zip(
        artifact_dir, copied_files, titles, target_language, errors=errors
    )

    manifest = {
        "task_id": task_id,
        "task_type": task.get("type", "task"),
        "summary": task.get("summary", ""),
        "status": task.get("status", "done"),
        "record_state": (
            existing_record.get("record_state", HISTORY_RECORD_ACTIVE)
            if existing_record
            else HISTORY_RECORD_ACTIVE
        ),
        "created_at": task.get("created_at", ""),
        "updated_at": task.get("updated_at", ""),
        "completed_at": datetime.now().isoformat(),
        "trashed_at": "",
        "purged_at": "",
        "target_language": target_language,
        "titles": titles,
        "errors": errors,
        "progress": task.get("progress", {}),
        "file_paths": copied_files,
        "input_file_paths": copied_input_paths,
        "zip_path": zip_path,
        "artifact_dir": str(artifact_dir),
        "project_name": artifact_dir.name,
        "provider_id": (task.get("payload", {}) or {}).get("provider_id", ""),
        "payload": payload_snapshot,
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = [r for r in data.get("records", []) if r.get("task_id") != task_id]
    records.append(manifest)
    data["records"] = records
    save_history_data(data)
    return manifest


def trash_history_record(task_id: str):
    data = get_history_data()
    record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    if not record:
        return None
    for item in data.get("records", []):
        if item.get("task_id") != task_id:
            continue
        item["record_state"] = HISTORY_RECORD_TRASHED
        item["trashed_at"] = datetime.now().isoformat()
        item["updated_at"] = datetime.now().isoformat()
    save_history_data(data)
    updated_record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    if updated_record:
        write_manifest_record(_normalize_history_record(updated_record))
    return _normalize_history_record(updated_record or record)


def restore_history_record(task_id: str):
    data = get_history_data()
    record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    if not record:
        return None
    for item in data.get("records", []):
        if item.get("task_id") != task_id:
            continue
        item["record_state"] = HISTORY_RECORD_ACTIVE
        item["trashed_at"] = ""
        item["updated_at"] = datetime.now().isoformat()
    save_history_data(data)
    updated_record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    if updated_record:
        write_manifest_record(_normalize_history_record(updated_record))
    return _normalize_history_record(updated_record or record)


def delete_history_record(task_id: str):
    data = get_history_data()
    record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    data["records"] = [
        r for r in data.get("records", []) if r.get("task_id") != task_id
    ]
    save_history_data(data)
    if record and record.get("artifact_dir"):
        shutil.rmtree(record.get("artifact_dir"), ignore_errors=True)
    return record


def trash_history_records_by_status(statuses):
    status_set = {str(status or "").strip() for status in (statuses or []) if status}
    if not status_set:
        return []
    data = get_history_data()
    moved_records = [
        _normalize_history_record(r)
        for r in data.get("records", [])
        if r.get("status") in status_set
        and (r.get("record_state") or HISTORY_RECORD_ACTIVE) == HISTORY_RECORD_ACTIVE
    ]
    if not moved_records:
        return []
    now = datetime.now().isoformat()
    for record in data.get("records", []):
        if record.get("status") not in status_set:
            continue
        if (record.get("record_state") or HISTORY_RECORD_ACTIVE) != HISTORY_RECORD_ACTIVE:
            continue
        record["record_state"] = HISTORY_RECORD_TRASHED
        record["trashed_at"] = now
        record["updated_at"] = now
    save_history_data(data)
    return moved_records


def purge_history_records_by_status(statuses):
    status_set = {str(status or "").strip() for status in (statuses or []) if status}
    if not status_set:
        return []
    data = get_history_data()
    removed_records = [
        _normalize_history_record(r)
        for r in data.get("records", [])
        if r.get("status") in status_set
        and (r.get("record_state") or HISTORY_RECORD_ACTIVE) == HISTORY_RECORD_TRASHED
    ]
    if not removed_records:
        return []
    data["records"] = [
        r
        for r in data.get("records", [])
        if not (
            r.get("status") in status_set
            and (r.get("record_state") or HISTORY_RECORD_ACTIVE)
            == HISTORY_RECORD_TRASHED
        )
    ]
    save_history_data(data)
    for record in removed_records:
        artifact_dir = record.get("artifact_dir")
        if artifact_dir:
            shutil.rmtree(artifact_dir, ignore_errors=True)
    return removed_records


def purge_trashed_history_record(task_id: str):
    data = get_history_data()
    record = next(
        (r for r in data.get("records", []) if r.get("task_id") == task_id), None
    )
    if not record:
        return None
    if (record.get("record_state") or HISTORY_RECORD_ACTIVE) != HISTORY_RECORD_TRASHED:
        return None
    return delete_history_record(task_id)


def purge_all_trashed_history_records():
    return purge_history_records_by_status(
        {"done", "error", "cancelled", "expired"}
    )


def format_bytes(num_bytes: int):
    value = float(num_bytes or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{int(num_bytes)} B"


def get_path_size(path: Path):
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def summarize_record_files(record: dict):
    file_paths = list(record.get("file_paths", []) or [])
    input_paths = list(record.get("input_file_paths", []) or [])
    zip_path = record.get("zip_path", "")
    artifact_dir = record.get("artifact_dir", "")
    checked_paths = file_paths + input_paths
    if zip_path:
        checked_paths.append(zip_path)
    missing_paths = [path for path in checked_paths if path and not Path(path).exists()]
    artifact_exists = bool(artifact_dir) and Path(artifact_dir).exists()
    size_bytes = get_path_size(Path(artifact_dir)) if artifact_exists else 0
    return {
        "file_count": len(file_paths),
        "input_count": len(input_paths),
        "missing_count": len(missing_paths),
        "missing_paths": missing_paths,
        "artifact_exists": artifact_exists,
        "size_bytes": size_bytes,
    }


def open_record_output(record: dict):
    return open_in_file_manager(record.get("artifact_dir") or record.get("zip_path", ""))


def activate_confirmation(confirm_key: str):
    st.session_state[confirm_key] = True


def clear_confirmation(confirm_key: str):
    st.session_state.pop(confirm_key, None)


def render_confirmation_bar(
    confirm_key: str,
    message: str,
    confirm_label: str = "确认",
    cancel_label: str = "取消",
    confirm_type: str = "primary",
):
    if not st.session_state.get(confirm_key):
        return False
    st.warning(message)
    c1, c2 = st.columns(2)
    with c1:
        if st.button(confirm_label, key=f"{confirm_key}_confirm", type=confirm_type):
            clear_confirmation(confirm_key)
            return True
    with c2:
        if st.button(cancel_label, key=f"{confirm_key}_cancel"):
            clear_confirmation(confirm_key)
            st.rerun()
    return False


def render_template_item_preview(item: dict, group_meta: dict, item_meta: dict):
    icon = item.get("icon", "📦")
    enabled = item.get("enabled", True)
    hint = (item.get("hint") or "").strip()
    usage_note = item_meta.get("usage_note", "")
    state_class = "" if enabled else "disabled"
    enabled_badge_class = "template-preview-badge" if enabled else "template-preview-badge off"
    enabled_text = "已启用" if enabled else "已停用"
    st.markdown(
        f"""
        <div class="template-preview-shell">
            <div class="template-preview-title">实时预览</div>
            <div class="template-preview-subtitle">你现在看到的是模板在后台中的展示效果，不需要保存就能先预览。</div>
            <div class="template-preview-card {state_class}">
                <span class="{enabled_badge_class}">{enabled_text}</span>
                <span class="template-preview-badge">适用页面: {group_meta.get('page_label', '未定义')}</span>
                <div class="template-preview-name">{icon} {item.get('name', '未命名模板')}</div>
                <div class="template-preview-desc">{item.get('desc', '暂无说明')}</div>
                <div class="template-preview-hint">用途提示: {usage_note or '暂无用途说明'}</div>
                <div class="template-preview-hint">提示语: {hint or '无'}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_template_group_preview(group_key: str, group_meta: dict, group: dict):
    enabled_items = [
        item for _, item in sorted(
            group.items(), key=lambda pair: (pair[1].get("order", 999), pair[0])
        )
    ]
    if not enabled_items:
        return
    cards = []
    for item in enabled_items:
        card_class = "template-preview-mini" if item.get("enabled", True) else "template-preview-mini disabled"
        cards.append(
            f"""
            <div class="{card_class}">
                <div>{item.get('icon', '📦')}</div>
                <div class="template-preview-mini-name">{item.get('name', '未命名模板')}</div>
                <div class="template-preview-mini-meta">排序: {int(item.get('order', 1))}</div>
                <div class="template-preview-mini-meta">{'启用中' if item.get('enabled', True) else '已停用'}</div>
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="template-preview-shell">
            <div class="template-preview-title">{group_meta.get('title', group_key)} 工作流预览</div>
            <div class="template-preview-subtitle">模拟该工作流里模板选择区的呈现顺序与启用状态。</div>
            <div class="template-preview-grid">
                {''.join(cards)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _record_option_label(record: dict):
    status = _record_status_label(record.get("status"))
    title = record.get("summary") or record.get("task_type", "任务")
    completed_at = record.get("completed_at") or record.get("created_at", "")
    return f"{status} · {title} · {completed_at}"


def render_batch_record_actions(records: list, mode: str):
    if not records:
        return
    options = {record.get("task_id"): _record_option_label(record) for record in records}
    selected_ids = st.multiselect(
        "选择要批量处理的项目",
        options=list(options.keys()),
        format_func=lambda task_id: options.get(task_id, task_id),
        key=f"batch_select_{mode}",
        placeholder="可多选",
    )
    if not selected_ids:
        return
    selected_count = len(selected_ids)
    if mode == "history":
        confirm_key = "confirm_batch_trash_history"
        if st.button("🗑️ 批量移入回收站", key="batch_trash_history_trigger"):
            activate_confirmation(confirm_key)
            st.rerun()
        if render_confirmation_bar(
            confirm_key,
            f"将把所选 {selected_count} 条历史项目移入回收站，本地文件会先保留。",
            confirm_label="确认批量移入回收站",
        ):
            moved_count = len(trash_history_records_by_ids(selected_ids))
            st.success(f"已将 {moved_count} 条项目移入回收站。")
            st.rerun()
    elif mode == "trash":
        restore_key = "confirm_batch_restore_trash"
        purge_key = "confirm_batch_purge_trash"
        c1, c2 = st.columns(2)
        with c1:
            if st.button("♻️ 批量恢复", key="batch_restore_trash_trigger"):
                activate_confirmation(restore_key)
                st.rerun()
        with c2:
            if st.button("🧨 批量彻底删除", key="batch_purge_trash_trigger"):
                activate_confirmation(purge_key)
                st.rerun()
        if render_confirmation_bar(
            restore_key,
            f"将把所选 {selected_count} 条回收站记录恢复到历史项目。",
            confirm_label="确认批量恢复",
        ):
            restored_count = len(restore_history_records_by_ids(selected_ids))
            st.success(f"已恢复 {restored_count} 条记录。")
            st.rerun()
        if render_confirmation_bar(
            purge_key,
            f"将彻底删除所选 {selected_count} 条回收站记录及其本地文件，执行后不可恢复。",
            confirm_label="确认批量彻底删除",
        ):
            purged_count = len(purge_trashed_history_records_by_ids(selected_ids))
            st.success(f"已彻底删除 {purged_count} 条记录。")
            st.rerun()


def collect_diagnostics(records: list):
    orphan_dirs = find_orphan_project_dirs(records)
    missing_records = [
        record for record in records if summarize_record_files(record)["missing_count"] > 0
    ]
    manifest_count = len(iter_project_manifest_paths())
    provider = get_active_provider() or {}
    active_tasks = [task for task in list_tasks() if task.get("status") in {"queued", "running"}]
    return {
        "record_count": len(records),
        "manifest_count": manifest_count,
        "missing_record_count": len(missing_records),
        "orphan_dir_count": len(orphan_dirs),
        "active_task_count": len(active_tasks),
        "provider_name": provider.get("name", "未配置"),
        "output_dir": str(get_project_output_base_dir()),
        "orphan_dirs": orphan_dirs,
        "missing_records": missing_records,
    }


def collect_template_library_diagnostics():
    issues = []
    title_templates = get_title_templates()
    enabled_title_templates = get_enabled_title_templates()
    image_templates = get_templates()

    if not enabled_title_templates:
        issues.append("标题模板已全部停用，标题页将无法正常选择模板。")

    for key, template in title_templates.items():
        prompt = (template.get("prompt") or "").strip()
        if not prompt:
            issues.append(f"标题模板「{template.get('name', key)}」缺少 Prompt。")
            continue
        if "{product_info}" not in prompt and key != "image_analysis":
            issues.append(
                f"标题模板「{template.get('name', key)}」未包含 {{product_info}} 占位符，可能无法利用商品信息。"
            )

    translation_templates = image_templates.get("translation_types", {})
    enabled_translation = [
        template
        for template in translation_templates.values()
        if template.get("enabled", True)
    ]
    if not enabled_translation:
        issues.append("翻译保版模板已全部停用，翻译模式将无法正常选择模板。")

    for key, template in translation_templates.items():
        prompt = (template.get("prompt") or "").strip()
        if not prompt:
            issues.append(f"翻译模板「{template.get('name', key)}」缺少 Prompt。")
            continue
        if "{output_language_name}" not in prompt:
            issues.append(
                f"翻译模板「{template.get('name', key)}」未包含 {{output_language_name}} 占位符。"
            )
        if "{aspect_ratio}" not in prompt:
            issues.append(
                f"翻译模板「{template.get('name', key)}」未包含 {{aspect_ratio}} 占位符。"
            )

    return {
        "title_template_count": len(title_templates),
        "enabled_title_template_count": len(enabled_title_templates),
        "image_template_count": sum(len(group) for group in image_templates.values() if isinstance(group, dict)),
        "enabled_translation_count": len(enabled_translation),
        "issues": issues,
    }


def open_in_file_manager(path_str: str):
    if not runtime_supports_local_file_access():
        return False
    path = Path(path_str)
    target = path if path.is_dir() else path.parent
    if not target.exists():
        return False
    try:
        subprocess.run(["open", str(target)], check=False)
        return True
    except Exception:
        return False


def list_tasks():
    data = get_tasks_data()
    return sorted(
        data.get("tasks", []), key=lambda x: x.get("created_at", ""), reverse=True
    )


def clear_terminal_tasks():
    with TASK_LOCK:
        data = get_tasks_data()
        existing_tasks = data.get("tasks", [])
        active_tasks = [
            task
            for task in existing_tasks
            if task.get("status") not in TASK_STATUS_TERMINAL
        ]
        removed_count = len(existing_tasks) - len(active_tasks)
        data["tasks"] = active_tasks
        save_tasks_data(data)
        return removed_count


def update_task(task_id: str, **updates):
    with TASK_LOCK:
        data = get_tasks_data()
        for task in data.get("tasks", []):
            if task.get("id") == task_id:
                task.update(updates)
                task["updated_at"] = datetime.now().isoformat()
                if updates.get("status") == "running":
                    task.setdefault("started_at", datetime.now().isoformat())
                if updates.get("status") in TASK_STATUS_TERMINAL:
                    task.setdefault("ended_at", datetime.now().isoformat())
                save_tasks_data(data)
                return task
    return None


def prune_task_slots(tasks: list):
    while len(tasks) >= MAX_TASK_QUEUE:
        removable_index = next(
            (i for i, t in enumerate(tasks) if t.get("status") in TASK_STATUS_TERMINAL),
            None,
        )
        if removable_index is None:
            return False, tasks
        tasks.pop(removable_index)
    return True, tasks


def create_task(task_type: str, payload: dict):
    with TASK_LOCK:
        data = get_tasks_data()
        tasks = data.get("tasks", [])
        ok, tasks = prune_task_slots(tasks)
        if not ok:
            return (
                None,
                f"最多同时保留 {MAX_TASK_QUEUE} 个任务，请先清理已完成或失败任务。",
            )
        task = {
            "id": _new_task_id(),
            "type": task_type,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "payload": payload,
            "progress": {"done": 0, "total": payload.get("total", 0)},
            "errors": [],
            "titles": [],
            "result_files": [],
            "result_title_language": payload.get("target_language")
            or payload.get("title_language")
            or DEFAULT_TARGET_LANGUAGE,
            "summary": payload.get("summary", ""),
        }
        tasks.append(task)
        data["tasks"] = tasks
        save_tasks_data(data)
        return task, ""


def cancel_task(task_id: str):
    task = update_task(task_id, status="cancelled")
    if task:
        record_task_history(
            task,
            {
                "titles": task.get("titles", []),
                "errors": ["用户手动取消任务"],
                "files": task.get("result_files", []),
                "target_language": task.get(
                    "result_title_language", DEFAULT_TARGET_LANGUAGE
                ),
            },
        )
    return bool(task)


def is_task_cancelled(task_id: str) -> bool:
    task = next((t for t in list_tasks() if t.get("id") == task_id), None)
    return bool(task and task.get("status") == "cancelled")


def ensure_task_not_cancelled(task_id: str):
    if is_task_cancelled(task_id):
        raise Exception("任务已取消")


def normalize_running_tasks():
    data = get_tasks_data()
    task_threads = get_task_threads()
    changed = False
    for task in data.get("tasks", []):
        if task.get("status") != "running":
            continue
        th = task_threads.get(task.get("id"))
        if th and th.is_alive():
            continue
        task["status"] = "expired"
        task.setdefault("errors", []).append(
            "任务在后台中断或页面刷新后未恢复，请重新提交。"
        )
        task["updated_at"] = datetime.now().isoformat()
        record_task_history(
            task,
            {
                "titles": task.get("titles", []),
                "errors": task.get("errors", []),
                "files": task.get("result_files", []),
                "target_language": task.get(
                    "result_title_language", DEFAULT_TARGET_LANGUAGE
                ),
            },
        )
        changed = True
    if changed:
        save_tasks_data(data)


def persist_image_for_task(img: Image.Image, filename: str):
    task_dir = DATA_DIR / "task_results"
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / filename
    img.save(path, format="PNG")
    return str(path)


def load_image_paths(paths: list):
    images = []
    for path in paths or []:
        try:
            images.append(Image.open(path).convert("RGB"))
        except Exception:
            continue
    return images


def _run_with_timeout(func, timeout_seconds: int):
    result = {}
    error = {}
    done = threading.Event()

    def _runner():
        try:
            result["value"] = func()
        except Exception as exc:
            error["value"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    if not done.wait(max(1, int(timeout_seconds))):
        raise TimeoutError(f"Gemini request timed out after {timeout_seconds}s")
    if "value" in error:
        raise error["value"]
    return result.get("value")


def get_compliance():
    c = load_json(COMPLIANCE_FILE, DEFAULT_COMPLIANCE)
    for k, v in DEFAULT_COMPLIANCE.items():
        if k not in c:
            c[k] = v
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


def _normalize_template_item(group_key: str, item_key: str, item: dict):
    # Normalize every template item before UI/render/runtime use so downstream code
    # can rely on stable keys like name/desc/enabled/order without repetitive guards.
    default_item = copy.deepcopy(
        (DEFAULT_TEMPLATES.get(group_key, {}) or {}).get(item_key, {})
    )
    merged = copy.deepcopy(default_item)
    merged.update(copy.deepcopy(item or {}))
    meta = TEMPLATE_ITEM_META.get(group_key, {}).get(item_key, {})
    if not (merged.get("name") or "").strip():
        merged["name"] = meta.get("recommended_name", item_key)
    if not (merged.get("desc") or "").strip():
        merged["desc"] = meta.get("recommended_desc", "")
    merged["enabled"] = bool(merged.get("enabled", True))
    try:
        merged["order"] = int(merged.get("order", 999))
    except Exception:
        merged["order"] = 999
    return merged


def _normalize_template_group(group_key: str, group: dict):
    normalized = {}
    default_group = (DEFAULT_TEMPLATES.get(group_key, {}) or {})
    source_group = group if isinstance(group, dict) else {}
    item_keys = list(dict.fromkeys([*default_group.keys(), *source_group.keys()]))
    for item_key in item_keys:
        normalized[item_key] = _normalize_template_item(
            group_key, item_key, source_group.get(item_key, default_group.get(item_key, {}))
        )
    return normalized


def get_templates():
    # Product-facing template management is allowed to evolve independently from
    # persisted JSON shape, so all template reads go through this normalization layer.
    t = load_json(TEMPLATES_FILE, DEFAULT_TEMPLATES)
    normalized = {}
    for group_key in TEMPLATE_GROUP_ORDER:
        normalized[group_key] = _normalize_template_group(
            group_key, (t or {}).get(group_key, {})
        )
    for group_key, group_value in (t or {}).items():
        if group_key in normalized:
            continue
        normalized[group_key] = copy.deepcopy(group_value)
    changed = False
    # Safe display migration: only rewrite exact old default names/descriptions.
    legacy_updates = {
        ("combo_types", "feature"): ("功能卖点", "核心功能展示图"),
        ("combo_types", "scene"): ("场景应用", "使用场景展示"),
        ("combo_types", "detail"): ("细节特写", "工艺细节放大"),
        ("combo_types", "size"): ("尺寸规格", "尺寸标注图"),
        ("combo_types", "compare"): ("对比优势", "竞品对比图"),
        ("combo_types", "package"): ("清单展示", "包装内容物"),
        ("combo_types", "steps"): ("使用步骤", "操作步骤图"),
    }
    for (group_key, item_key), (legacy_name, legacy_desc) in legacy_updates.items():
        item = ((normalized or {}).get(group_key, {}) or {}).get(item_key, {})
        meta = TEMPLATE_ITEM_META.get(group_key, {}).get(item_key, {})
        if not item or not meta:
            continue
        if (item.get("name") or "").strip() == legacy_name:
            item["name"] = meta.get("recommended_name", legacy_name)
            changed = True
        if (item.get("desc") or "").strip() == legacy_desc:
            item["desc"] = meta.get("recommended_desc", legacy_desc)
            changed = True
    if changed:
        save_templates(normalized)
    return normalized


def save_templates(data):
    # Save through the same normalization path to avoid writing partial/dirty state
    # back to disk from the settings UI.
    normalized = {}
    source = data if isinstance(data, dict) else {}
    for group_key in TEMPLATE_GROUP_ORDER:
        normalized[group_key] = _normalize_template_group(
            group_key, source.get(group_key, {})
        )
    for group_key, group_value in source.items():
        if group_key in normalized:
            continue
        normalized[group_key] = copy.deepcopy(group_value)
    return save_json(TEMPLATES_FILE, normalized)


def get_template_group(group_key: str):
    return get_templates().get(group_key, {})


def get_sorted_templates(group_key: str, enabled_only: bool = False):
    group = get_template_group(group_key)
    items = group.items()
    if enabled_only:
        items = [(key, value) for key, value in items if value.get("enabled", True)]
    return sorted(items, key=lambda item: (item[1].get("order", 999), item[0]))


def get_enabled_template_group(group_key: str):
    return {key: value for key, value in get_sorted_templates(group_key, enabled_only=True)}


def _normalize_title_template_item(template_key: str, item: dict):
    default_item = copy.deepcopy(DEFAULT_TITLE_TEMPLATES.get(template_key, {}))
    merged = copy.deepcopy(default_item)
    merged.update(copy.deepcopy(item or {}))
    if not (merged.get("name") or "").strip():
        merged["name"] = default_item.get("name", template_key)
    if not (merged.get("desc") or "").strip():
        merged["desc"] = default_item.get("desc", "")
    if not (merged.get("prompt") or "").strip():
        merged["prompt"] = default_item.get("prompt", "")
    merged["enabled"] = bool(merged.get("enabled", True))
    return merged


def get_title_templates():
    t = load_json(TITLE_TEMPLATES_FILE, DEFAULT_TITLE_TEMPLATES)
    normalized = {}
    for template_key in DEFAULT_TITLE_TEMPLATES.keys():
        normalized[template_key] = _normalize_title_template_item(
            template_key, (t or {}).get(template_key, {})
        )
    for template_key, template_value in (t or {}).items():
        if template_key in normalized:
            continue
        normalized[template_key] = _normalize_title_template_item(
            template_key, template_value
        )
    return normalized


def save_title_templates(data):
    source = data if isinstance(data, dict) else {}
    normalized = {}
    for template_key in DEFAULT_TITLE_TEMPLATES.keys():
        normalized[template_key] = _normalize_title_template_item(
            template_key, source.get(template_key, {})
        )
    for template_key, template_value in source.items():
        if template_key in normalized:
            continue
        normalized[template_key] = _normalize_title_template_item(
            template_key, template_value
        )
    return save_json(TITLE_TEMPLATES_FILE, normalized)


def get_enabled_title_templates():
    return {
        key: value
        for key, value in get_title_templates().items()
        if value.get("enabled", True)
    }


def get_title_template_by_key(template_key: str):
    templates = get_title_templates()
    return templates.get(template_key, templates.get("default", {}))


def get_title_template_prompt(template_key: str):
    template = get_title_template_by_key(template_key)
    return template.get("prompt", DEFAULT_TITLE_TEMPLATES["default"]["prompt"])


def build_template_selector_options(
    templates: dict,
    include_custom: bool = False,
    custom_label: str = "✏️ 自定义提示词",
    priority_keys: list = None,
):
    priority_keys = list(priority_keys or [])
    options = []
    for key in priority_keys:
        if key in templates and key not in options:
            options.append(key)
    for key in templates.keys():
        if key not in options:
            options.append(key)
    if include_custom:
        options = ["custom"] + options
    labels = {"custom": custom_label}
    labels.update({key: value.get("name", key) for key, value in templates.items()})
    return options, labels


def build_title_template_selector_options(
    input_mode: str = "",
    include_custom: bool = False,
):
    enabled_templates = get_enabled_title_templates()
    priority_keys = ["image_analysis"] if input_mode == "🖼️ 图片分析" else []
    template_options, template_names = build_template_selector_options(
        enabled_templates,
        include_custom=include_custom,
        custom_label="✏️ 自定义提示词",
        priority_keys=priority_keys,
    )
    return enabled_templates, template_options, template_names


def build_translation_template_selector_options():
    enabled_templates = get_enabled_template_group("translation_types")
    template_options, template_names = build_template_selector_options(
        enabled_templates,
        include_custom=False,
        priority_keys=["preserve_layout"],
    )
    return enabled_templates, template_options, template_names


def get_target_language(code: str) -> dict:
    return TARGET_LANGUAGE_MAP.get(code, TARGET_LANGUAGE_MAP[DEFAULT_TARGET_LANGUAGE])


def format_target_language_option(code: str) -> str:
    info = get_target_language(code)
    return f"{info['flag']} {info['label']} / {info['native_name']}"


def get_title_language_caption(code: str) -> str:
    info = get_target_language(code)
    return f"{info['flag']} {info['label']} ({info['english_name']})"


def render_target_language_selector(
    prefix: str,
    key_suffix: str,
    label: str,
    help_text: str,
):
    s = get_settings()
    options = [item["code"] for item in TARGET_LANGUAGES]
    default_code = (
        s.get("default_image_language", DEFAULT_TARGET_LANGUAGE)
        if "image" in key_suffix
        else s.get("default_title_language", DEFAULT_TARGET_LANGUAGE)
    )
    if default_code not in options:
        default_code = DEFAULT_TARGET_LANGUAGE
    default_index = options.index(default_code)
    return st.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=format_target_language_option,
        key=f"{prefix}_{key_suffix}",
        help=help_text,
    )


def fill_prompt_template(template: str, **values) -> str:
    text = template or ""
    for key, value in values.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text


def clean_generated_copy(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned[:max_chars]


def build_title_prompt(
    template_prompt: str, product_info: str, target_language: str
) -> str:
    lang = get_target_language(target_language)
    prompt = fill_prompt_template(
        template_prompt,
        product_info=product_info,
        target_language_name=lang["english_name"],
        target_language_native=lang["native_name"],
        target_language_label=lang["label"],
    )
    if target_language == "en":
        return (
            f"{prompt}\n\n"
            "TARGET LANGUAGE RULES\n"
            "- Output English only.\n"
            "- Generate exactly 3 English titles with no translation lines.\n"
            f"- Every English title must be {MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS} characters.\n"
            "- Output exactly 3 lines total with no labels or commentary."
        )

    extra_rule = (
        "Use Simplified Chinese for every translation line."
        if target_language == "zh"
        else f"Do not output Chinese. Use {lang['english_name']} only for every translation line."
    )
    return (
        f"{prompt}\n\n"
        "TARGET LANGUAGE RULES\n"
        "- Keep English as the fixed source language for every first line.\n"
        f"- The second line of each title must be in {lang['english_name']} ({lang['native_name']}).\n"
        f"- {extra_rule}\n"
        "- Output exactly 6 lines total with no labels or commentary.\n"
        f"- Line order must be English line then {lang['english_name']} line, repeated 3 times."
    )


def get_image_language_instruction(target_language: str) -> str:
    lang = get_target_language(target_language)
    return (
        f"If the image contains any text, ALL text MUST be in {lang['english_name']} "
        f"({lang['native_name']}) only. Do not mix multiple languages."
    )


def get_compliance_prompt(mode=None) -> str:
    if mode is None:
        mode = st.session_state.get("user_compliance_mode", "strict")
    comp = get_compliance()
    preset = comp.get("presets", {}).get(
        mode, comp.get("presets", {}).get("strict", {})
    )
    blacklist = sorted(
        set(preset.get("blacklist", [])) | set(comp.get("custom_blacklist", []))
    )
    whitelist = sorted(set(comp.get("whitelist", [])))
    lines = []
    if blacklist:
        lines.append("Avoid these words or claims: " + ", ".join(blacklist[:30]))
    if whitelist:
        lines.append(
            "These whitelist terms are allowed when needed: "
            + ", ".join(whitelist[:20])
        )
    lines.append(
        "Prefer neutral, platform-safe wording and keep the translation faithful."
    )
    return "\n".join(lines)


def build_translation_prompt(
    target_language: str,
    aspect: str,
    compliance_mode: str,
    template_key: str = "preserve_layout",
) -> str:
    language_info = get_target_language(target_language)
    # Translation templates are now real runtime assets. Prompt selection must
    # come from the enabled template group instead of a hard-coded default.
    translation_templates = get_enabled_template_group("translation_types")
    template = translation_templates.get(
        template_key,
        get_template_group("translation_types").get("preserve_layout", {}),
    )
    prompt_template = (
        template.get("prompt")
        or DEFAULT_PROMPTS["translation_image_prompt"]
    )
    return fill_prompt_template(
        prompt_template,
        output_language_name=language_info["english_name"],
        aspect_ratio=aspect,
        compliance_rules=get_compliance_prompt(compliance_mode),
    )


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


def _strip_code_fence(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_title_lines(text: str) -> list:
    if not text:
        return []
    cleaned_text = _strip_code_fence(text)
    lines = [l.strip() for l in cleaned_text.split("\n") if l.strip()]
    clean_lines = []
    line_prefix_pattern = "|".join(re.escape(prefix) for prefix in TITLE_LINE_PREFIXES)
    for line in lines:
        cleaned = re.sub(
            rf"^(Title\s*\d*[:.]?\s*|Option\s*\d*[:.]?\s*|\d+[:.]\s*|(?:{line_prefix_pattern})[:：]\s*)",
            "",
            line,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            clean_lines.append(cleaned)
    return clean_lines


def _validate_bilingual_titles(lines: list) -> tuple:
    details = {"line_count": len(lines), "invalid_en_lengths": []}
    if len(lines) != 6:
        return False, f"输出行数为{len(lines)}，需为6行", details
    for idx, line in enumerate(lines):
        if not line:
            return False, f"第{idx + 1}行为空", details
        if idx % 2 == 0:
            en_len = len(line)
            if en_len < MIN_TITLE_EN_CHARS or en_len > MAX_TITLE_EN_CHARS:
                details["invalid_en_lengths"].append({"index": idx, "length": en_len})
    if details["invalid_en_lengths"]:
        return (
            False,
            f"英文行长度不符合{MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS}字符要求",
            details,
        )
    return True, "", details


def _validate_title_output(lines: list, target_language: str) -> tuple:
    if target_language == "en":
        details = {"line_count": len(lines), "invalid_en_lengths": []}
        if len(lines) != 3:
            return False, f"输出行数为{len(lines)}，需为3行英文标题", details
        for idx, line in enumerate(lines):
            if not line:
                return False, f"第{idx + 1}行为空", details
            en_len = len(line)
            if en_len < MIN_TITLE_EN_CHARS or en_len > MAX_TITLE_EN_CHARS:
                details["invalid_en_lengths"].append({"index": idx, "length": en_len})
        if details["invalid_en_lengths"]:
            return (
                False,
                f"英文行长度不符合{MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS}字符要求",
                details,
            )
        return True, "", details
    return _validate_bilingual_titles(lines)


def _build_title_result(
    success: bool,
    titles: list = None,
    raw_text: str = "",
    error_type: str = "",
    error_message: str = "",
    retryable: bool = False,
    attempt_count: int = 1,
    input_mode: str = "text",
    details: dict = None,
):
    return {
        "success": success,
        "titles": titles or [],
        "raw_text": raw_text or "",
        "error_type": error_type or "",
        "error_message": error_message or "",
        "retryable": retryable,
        "attempt_count": attempt_count,
        "input_mode": input_mode,
        "details": details or {},
        "target_language": details.get("target_language") if details else "",
    }


def _classify_title_error(error_message: str) -> tuple:
    msg = (error_message or "").lower()
    if "api key" in msg or "apikey" in msg or "unauthorized" in msg:
        return "missing_api_key", False
    if "failed_precondition" in msg or "user location is not supported" in msg:
        return "location_restricted", False
    if "model" in msg and (
        "not found" in msg
        or "unsupported" in msg
        or "invalid" in msg
        or "not available" in msg
    ):
        return "model_not_supported", False
    if (
        "base_url" in msg
        or "base url" in msg
        or "404" in msg
        or "connection" in msg
        or "connect" in msg
        or "timeout" in msg
        or "timed out" in msg
        or "dns" in msg
        or "name or service not known" in msg
        or "refused" in msg
        or "unreachable" in msg
        or "failed to establish" in msg
    ):
        return "provider_error", False
    return "upstream_error", False


def format_title_error(result: dict) -> str:
    error_type = result.get("error_type") or ""
    base = "标题生成失败"
    if error_type == "missing_api_key":
        return f"{base}：未配置有效API Key。请在「提供商设置」中填写。"
    if error_type == "model_not_supported":
        return (
            f"{base}：标题/视觉模型不可用或不支持当前提供商。请检查模型名称或Base URL。"
        )
    if error_type == "provider_error":
        return f"{base}：提供商连接失败。请检查Base URL 或网络。"
    if error_type == "location_restricted":
        return f"{base}：已连通 Google，但当前账号或地区不支持该 API 调用。"
    if error_type == "invalid_format":
        return f"{base}：输出格式不符合预期（英文单语或英文+目标语言）或英文长度要求，已自动重试。"
    if error_type == "retry_exhausted":
        return f"{base}：输出格式仍不符合预期（英文单语或英文+目标语言）（已重试1次）。建议调整商品信息或模板提示词。"
    if error_type == "input_missing":
        return f"{base}：缺少必要的商品信息或图片。"
    return f"{base}：上游请求失败，请稍后重试。"


def sanitize_task_error(message: str, fallback: str = "任务执行失败") -> str:
    msg = str(message or "").strip()
    if not msg:
        return fallback
    low = msg.lower()
    if "failed_precondition" in low or "user location is not supported" in low:
        return "Google API 当前账号或地区不支持该调用。"
    if "resource has been exhausted" in low or "proxy_config_error" in low:
        return "中转站上游配额已用尽，请稍后重试或切换其他模型/提供商。"
    if "timeout" in low or "timed out" in low:
        return "请求超时，请检查网络、代理或模型响应速度。"
    if "api key" in low or "unauthorized" in low:
        return "API Key 无效或未配置。"
    if "failed to decode base64 data" in low or "illegal base64" in low:
        return "中转站图片输入格式不兼容，已切换为兼容模式后请重试。"
    if (
        "base_url" in low
        or "base url" in low
        or "connect" in low
        or "connection" in low
        or "dns" in low
        or "refused" in low
        or "unreachable" in low
    ):
        return "提供商连接失败，请检查 Base URL、代理或网络。"
    msg = re.sub(r"(https?://)([^:/@\s]+):([^/@\s]+)@", r"\1***:***@", msg)
    msg = re.sub(r"\s+", " ", msg)
    return msg[:180] or fallback


# ==================== AI客户端 (V15.2修复版) ====================
class GeminiClient:
    """Gemini 3 Pro Image 客户端 - V15.2修复版"""

    def __init__(
        self,
        api_key,
        model="gemini-3.1-flash-image-preview",
        base_url="",
        title_model="",
        vision_model="",
    ):
        s = get_settings()
        self.api_key = api_key
        self.model = model or s.get("default_model", "gemini-3.1-flash-image-preview")
        self.base_url = (base_url or "").strip()
        self.title_model = title_model or s.get(
            "default_title_model", "gemini-3.1-flash-lite-preview"
        )
        self.vision_model = vision_model or s.get(
            "default_vision_model", "gemini-3.1-flash-lite-preview"
        )
        client_kwargs = {
            "api_key": api_key,
            "http_options": types.HttpOptions(
                base_url=base_url or None,
                timeout=GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS * 1000,
            ),
        }
        self.client = genai.Client(**client_kwargs)
        self.prompts = self._load_prompts_safe()
        self.total_tokens = 0
        self.last_error = None

    def _load_prompts_safe(self):
        prompts = get_prompts()
        for key, default_value in DEFAULT_PROMPTS.items():
            if key not in prompts or not prompts[key]:
                prompts[key] = default_value
        return prompts

    def _call(
        self, func, retries=3, timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS
    ):
        timeout_seconds = max(
            1, int(timeout_seconds or GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS)
        )
        for i in range(retries):
            try:
                return _run_with_timeout(func, timeout_seconds)
            except Exception as e:
                self.last_error = str(e)
                err = str(e).lower()
                if "quota" in err:
                    raise Exception("⚠️ API配额已用尽")
                if "timeout" in err or "timed out" in err:
                    raise Exception(f"⚠️ 请求超时（{timeout_seconds}s）")
                if "network" in err or "connection" in err:
                    if i < retries - 1:
                        time.sleep(2**i)
                        continue
                    raise Exception("⚠️ 网络连接失败")
                if "rate" in err or "429" in err:
                    if i < retries - 1:
                        time.sleep(3)
                        continue
                    raise Exception("⚠️ 请求过于频繁")
                if i < retries - 1:
                    time.sleep(1)
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

    def _prep_inline_image_parts(self, images, max_count=3):
        parts = []
        for img in images[:max_count]:
            buf = io.BytesIO()
            ic = img.copy()
            if max(ic.size) > 1024:
                ic.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            ic.save(buf, format="PNG", optimize=True)
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(buf.getvalue()).decode(),
                    }
                }
            )
        return parts

    def _manual_generate_content(
        self,
        model: str,
        parts: list,
        response_modalities: list,
        aspect: str = "1:1",
        size: str = "1K",
        thinking_level: str = "high",
        timeout_seconds: int = GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
    ):
        payload = {"contents": [{"parts": parts}]}
        generation_config = {"responseModalities": response_modalities}
        if "IMAGE" in response_modalities:
            generation_config["imageConfig"] = {"aspectRatio": aspect}
            if self.model == "gemini-3-pro-image-preview" and size in ["2K", "4K"]:
                generation_config["imageConfig"]["imageSize"] = size
            if self.model == "gemini-3-pro-image-preview":
                generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
        payload["generationConfig"] = generation_config
        endpoint = f"{self.base_url.rstrip('/')}/v1beta/models/{model}:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            raise Exception(sanitize_task_error(body or str(e)))
        except Exception as e:
            raise Exception(sanitize_task_error(str(e)))

    def _count_manual_tokens(self, response_data: dict):
        try:
            tokens = (
                ((response_data or {}).get("usageMetadata") or {}).get(
                    "totalTokenCount"
                )
            ) or 0
            self.total_tokens += tokens
            return tokens
        except Exception:
            return 0

    def _extract_text_from_manual_response(self, response_data: dict) -> str:
        try:
            parts = (
                ((response_data or {}).get("candidates") or [])[0].get("content") or {}
            ).get("parts") or []
            texts = [part.get("text", "") for part in parts if part.get("text")]
            return "\n".join(texts).strip()
        except Exception:
            return ""

    def _extract_image_from_manual_response(self, response_data: dict):
        try:
            parts = (
                ((response_data or {}).get("candidates") or [])[0].get("content") or {}
            ).get("parts") or []
        except Exception:
            parts = []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            img_data = inline.get("data")
            if img_data:
                try:
                    return Image.open(io.BytesIO(base64.b64decode(img_data)))
                except Exception:
                    continue
            text = (part.get("text") or "").strip()
            if not text:
                continue
            match = re.search(r"https?://[^)\s]+", text)
            if not match:
                continue
            url = match.group(0)
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    return Image.open(io.BytesIO(resp.read()))
            except Exception:
                continue
        return None

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
        return sanitize_task_error(self.last_error)

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
            if self.base_url:
                response_data = self._manual_generate_content(
                    self.vision_model,
                    self._prep_inline_image_parts(images, 5) + [{"text": prompt}],
                    ["TEXT"],
                    timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                )
                self._count_manual_tokens(response_data)
                text = self._extract_text_from_manual_response(response_data)
            else:
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=self.vision_model,
                        contents=parts,
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT"]
                        ),
                    ),
                    timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                )
                self._count_tokens(resp)
                text = resp.text if resp.text else ""

            if text:
                result = self._parse_json_response(text, default_result)
                for key, value in default_result.items():
                    if key not in result or not result[key]:
                        result[key] = value
                return result
            return default_result
        except Exception as e:
            self.last_error = str(e)
            return default_result

    def generate_requirements(
        self, anchor, types_counts, tags=None, target_language="zh"
    ):
        templates = get_template_group("combo_types")
        types_str = ", ".join(
            [f"{templates[k]['name']}x{v}" for k, v in types_counts.items()]
        )
        language_info = get_target_language(target_language)

        prompt_template = self.prompts.get(
            "requirements_gen", DEFAULT_PROMPTS["requirements_gen"]
        )
        try:
            prompt = fill_prompt_template(
                prompt_template,
                product_name=anchor.get("product_name_zh", "商品"),
                category=anchor.get("primary_category", "General"),
                features=", ".join(anchor.get("visual_attrs", [])[:3]),
                tags=", ".join(tags) if tags else "无",
                types=types_str,
                output_language_name=language_info["english_name"],
                output_language_native=language_info["native_name"],
                output_language_label=language_info["label"],
            )
        except Exception:
            return []

        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=self.title_model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                ),
                timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
            )
            self._count_tokens(resp)
            result = self._parse_json_response(resp.text if resp.text else "[]", [])
            return result if isinstance(result, list) else []
        except Exception as e:
            self.last_error = str(e)
            return []

    def generate_en_copy(self, anchor, requirements, target_language="zh"):
        if not requirements:
            return requirements

        req_str = "\n".join(
            [f"- {r.get('type_name', '')}: {r.get('topic', '')}" for r in requirements]
        )
        language_info = get_target_language(target_language)
        prompt_template = self.prompts.get(
            "en_copy_gen", DEFAULT_PROMPTS["en_copy_gen"]
        )

        try:
            prompt = fill_prompt_template(
                prompt_template,
                product_name=anchor.get("product_name_en", "Product"),
                category=anchor.get("primary_category", "General"),
                requirements=req_str,
                output_language_name=language_info["english_name"],
                output_language_native=language_info["native_name"],
                output_language_label=language_info["label"],
            )
        except Exception:
            return requirements

        try:
            resp = self._call(
                lambda: self.client.models.generate_content(
                    model=self.title_model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(response_modalities=["TEXT"]),
                ),
                timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
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
                    r["headline"] = clean_generated_copy(
                        c.get("headline", ""), MAX_HEADLINE_CHARS
                    )
                    r["subline"] = clean_generated_copy(
                        c.get("subline", ""), MAX_SUBLINE_CHARS
                    )
                    r["badge"] = clean_generated_copy(
                        c.get("badge", ""), MAX_BADGE_CHARS
                    )
            return requirements
        except Exception as e:
            self.last_error = str(e)
            return requirements

    def compose_image_prompt(self, anchor, req, aspect="1:1", target_language="zh"):
        templates = get_template_group("combo_types")
        type_info = templates.get(req.get("type_key", ""), {})
        language_info = get_target_language(target_language)

        if req.get("type_key") == "size":
            prompt_template = self.prompts.get(
                "size_image_prompt", DEFAULT_PROMPTS["size_image_prompt"]
            )
            try:
                return fill_prompt_template(
                    prompt_template,
                    product_name=anchor.get("product_name_en", "Product"),
                    aspect_ratio=aspect,
                    output_language_name=language_info["english_name"],
                    output_language_native=language_info["native_name"],
                    output_language_label=language_info["label"],
                )
            except Exception:
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
            return fill_prompt_template(
                prompt_template,
                product_name=anchor.get("product_name_en", "Product"),
                category=anchor.get("primary_category", "General"),
                image_type=req.get("type_name", ""),
                style_hint=type_info.get("hint", ""),
                scene=req.get("scene", ""),
                text_content=text_content,
                aspect_ratio=aspect,
                output_language_name=language_info["english_name"],
                output_language_native=language_info["native_name"],
                output_language_label=language_info["label"],
            )
        except Exception:
            return f"Professional ecommerce product image. Product: {anchor.get('product_name_en', 'Product')}. Aspect: {aspect}"

    def generate_image(
        self,
        refs,
        prompt,
        aspect="1:1",
        size="1K",
        thinking_level="high",
        text_language="zh",
    ):
        """生成图片 - V15.2修复版，增加详细错误信息"""
        max_refs = MODELS.get(self.model, {}).get("max_refs", 3)
        parts = self._prep_images(refs, min(len(refs), max_refs))

        full_prompt = f"""CRITICAL: {get_image_language_instruction(text_language)}

{prompt}"""
        parts.append(full_prompt)

        # 构建配置 - 根据模型类型决定是否使用thinking_config
        image_config = types.ImageConfig(aspect_ratio=aspect)

        # 只有 Gemini 3 Pro 支持 image_size 和 thinking_level
        is_gemini3_pro = self.model == "gemini-3-pro-image-preview"

        if is_gemini3_pro and size in ["2K", "4K"]:
            image_config = types.ImageConfig(aspect_ratio=aspect, image_size=size)

        # 构建GenerateContentConfig - thinking_config只用于Gemini 3 Pro
        if is_gemini3_pro:
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=image_config,
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            )
        else:
            # gemini-2.5-flash-image 不支持 thinking_config
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"], image_config=image_config
            )

        try:
            if self.base_url:
                response_data = self._manual_generate_content(
                    self.model,
                    self._prep_inline_image_parts(refs, min(len(refs), max_refs))
                    + [{"text": full_prompt}],
                    ["IMAGE", "TEXT"],
                    aspect=aspect,
                    size=size,
                    thinking_level=thinking_level,
                    timeout_seconds=GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS,
                )
                self._count_manual_tokens(response_data)
                image = self._extract_image_from_manual_response(response_data)
                if image:
                    return image
            else:
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=self.model, contents=parts, config=config
                    ),
                    timeout_seconds=GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS,
                )
                self._count_tokens(resp)

                if resp.candidates:
                    for part in resp.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            img_data = part.inline_data.data
                            if img_data:
                                return Image.open(io.BytesIO(img_data))

            self.last_error = "API返回无图片数据"
            return None
        except Exception as e:
            self.last_error = str(e)
            raise e

    def generate_titles(self, product_info, template_prompt, target_language="zh"):
        if not self.api_key:
            return _build_title_result(
                False,
                error_type="missing_api_key",
                error_message="API Key未配置",
                retryable=False,
                attempt_count=0,
                input_mode="text",
            )

        language_info = get_target_language(target_language)
        prompt = build_title_prompt(template_prompt, product_info, target_language)
        last_raw = ""
        last_lines = []
        for attempt in range(1, 3):
            try:
                prompt_text = prompt
                if attempt == 2:
                    prompt_text = (
                        f"{prompt}\n\nSTRICT OUTPUT: Return exactly 6 lines, "
                        f"English then {language_info['english_name']} for each title, no extra lines."
                    )
                resp = self._call(
                    lambda: self.client.models.generate_content(
                        model=self.title_model,
                        contents=[prompt_text],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT"]
                        ),
                    ),
                    timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                )
                self._count_tokens(resp)
                text = resp.text.strip() if resp.text else ""
                lines = _parse_title_lines(text)
                valid, reason, details = _validate_title_output(lines, target_language)
                details["target_language"] = target_language
                if valid:
                    return _build_title_result(
                        True,
                        titles=lines[:6],
                        raw_text=text,
                        attempt_count=attempt,
                        input_mode="text",
                        details=details,
                    )

                last_raw = text
                last_lines = lines
                if attempt == 1:
                    continue
                return _build_title_result(
                    False,
                    titles=lines[:6],
                    raw_text=text,
                    error_type="retry_exhausted",
                    error_message=reason or "输出格式不符合要求",
                    retryable=False,
                    attempt_count=attempt,
                    input_mode="text",
                    details=details,
                )
            except Exception as e:
                self.last_error = str(e)
                error_type, retryable = _classify_title_error(str(e))
                if error_type == "upstream_error" and self.base_url:
                    error_type = "provider_error"
                return _build_title_result(
                    False,
                    titles=last_lines[:6],
                    raw_text=last_raw,
                    error_type=error_type,
                    error_message=str(e),
                    retryable=retryable,
                    attempt_count=attempt,
                    input_mode="text",
                )

        return _build_title_result(
            False,
            titles=last_lines[:6],
            raw_text=last_raw,
            error_type="invalid_format",
            error_message="输出格式不符合要求",
            retryable=False,
            attempt_count=2,
            input_mode="text",
            details={"line_count": len(last_lines)},
        )

    def generate_titles_from_image(
        self,
        images,
        product_info="",
        template_prompt=None,
        target_language="zh",
    ):
        """从图片分析生成商品标题"""
        if not self.api_key:
            return _build_title_result(
                False,
                error_type="missing_api_key",
                error_message="API Key未配置",
                retryable=False,
                attempt_count=0,
                input_mode="image",
            )
        if not images:
            return _build_title_result(
                False,
                error_type="input_missing",
                error_message="未提供图片",
                retryable=False,
                attempt_count=0,
                input_mode="image",
            )

        parts = self._prep_images(images, 5)

        if template_prompt is None:
            template_prompt = DEFAULT_TITLE_TEMPLATES.get("image_analysis", {}).get(
                "prompt", ""
            )

        language_info = get_target_language(target_language)
        prompt = build_title_prompt(
            template_prompt,
            product_info or "No additional info provided",
            target_language,
        )

        last_raw = ""
        last_lines = []
        for attempt in range(1, 3):
            try:
                prompt_text = prompt
                if attempt == 2:
                    prompt_text = (
                        f"{prompt}\n\nSTRICT OUTPUT: Return exactly 6 lines, "
                        f"English then {language_info['english_name']} for each title, no extra lines."
                    )
                if self.base_url:
                    response_data = self._manual_generate_content(
                        self.vision_model,
                        self._prep_inline_image_parts(images, 5)
                        + [{"text": prompt_text}],
                        ["TEXT"],
                        timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                    )
                    self._count_manual_tokens(response_data)
                    text = self._extract_text_from_manual_response(response_data)
                else:
                    parts_with_prompt = parts + [prompt_text]
                    resp = self._call(
                        lambda: self.client.models.generate_content(
                            model=self.vision_model,
                            contents=parts_with_prompt,
                            config=types.GenerateContentConfig(
                                response_modalities=["TEXT"]
                            ),
                        ),
                        timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                    )
                    self._count_tokens(resp)
                    text = resp.text.strip() if resp.text else ""
                lines = _parse_title_lines(text)
                valid, reason, details = _validate_title_output(lines, target_language)
                details["target_language"] = target_language
                if valid:
                    return _build_title_result(
                        True,
                        titles=lines[:6],
                        raw_text=text,
                        attempt_count=attempt,
                        input_mode="image",
                        details=details,
                    )

                last_raw = text
                last_lines = lines
                if attempt == 1:
                    continue
                return _build_title_result(
                    False,
                    titles=lines[:6],
                    raw_text=text,
                    error_type="retry_exhausted",
                    error_message=reason or "输出格式不符合要求",
                    retryable=False,
                    attempt_count=attempt,
                    input_mode="image",
                    details=details,
                )
            except Exception as e:
                self.last_error = str(e)
                error_type, retryable = _classify_title_error(str(e))
                if error_type == "upstream_error" and self.base_url:
                    error_type = "provider_error"
                return _build_title_result(
                    False,
                    titles=last_lines[:6],
                    raw_text=last_raw,
                    error_type=error_type,
                    error_message=str(e),
                    retryable=retryable,
                    attempt_count=attempt,
                    input_mode="image",
                )

        return _build_title_result(
            False,
            titles=last_lines[:6],
            raw_text=last_raw,
            error_type="invalid_format",
            error_message="输出格式不符合要求",
            retryable=False,
            attempt_count=2,
            input_mode="image",
            details={"line_count": len(last_lines)},
        )


# ==================== 图片转Base64工具 ====================
def image_to_base64(img: Image.Image) -> str:
    """将PIL Image转换为base64字符串"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64

    return base64.b64encode(buf.getvalue()).decode()


def create_zip_from_results(
    results: list, titles: list = None, target_language: str = "zh"
) -> bytes:
    """从结果创建ZIP文件"""
    buf = io.BytesIO()
    language_info = get_target_language(target_language)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in results:
            filename = item.get("filename", "image.png")
            img = item.get("image")
            if img:
                img_buf = io.BytesIO()
                img.save(img_buf, format="PNG")
                z.writestr(filename, img_buf.getvalue())

        if titles:
            if target_language == "en":
                titles_content = "\n\n".join(
                    [f"Title {i + 1}:\nEN: {t}" for i, t in enumerate(titles)]
                )
            else:
                titles_content = "\n\n".join(
                    [
                        f"标题 {i // 2 + 1}:\nEN: {titles[i]}\n{language_info['copy_tag']}: {titles[i + 1]}"
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
    :root { --primary: #6366f1; --success: #10b981; --warning: #f59e0b; --danger: #ef4444; }
    .main-title { font-size: 2.5rem; font-weight: 800; text-align: center; margin: 1rem 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .page-title { font-size: 1.75rem; font-weight: 700; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--primary); }
    .stButton>button { border-radius: 10px; font-weight: 600; transition: all 0.2s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3); }
    section[data-testid="stSidebar"] .stButton>button { padding: 0.38rem 0.65rem; min-height: 0; margin-bottom: 0.18rem; }
    section[data-testid="stSidebar"] h4 { margin-top: 0.15rem; margin-bottom: 0.45rem; font-size: 0.92rem; }
    section[data-testid="stSidebar"] .element-container { margin-bottom: 0.15rem; }
    section[data-testid="stSidebar"] hr { margin: 0.75rem 0; }
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
    .footer { margin-top: 2.5rem; padding: 1.1rem 0 0.35rem 0; border-top: 1px solid #e2e8f0; text-align: right; color: #64748b; font-size: 11px; }
    #MainMenu, footer, header { visibility: hidden; }
    .title-box { background: linear-gradient(135deg, #eff6ff 0%, #f5f3ff 100%); border: 1px solid #c7d2fe; border-radius: 12px; padding: 1rem; margin: 0.75rem 0; }
    .image-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.5rem; margin: 0.5rem 0; background: white; }
    .image-label { font-size: 12px; font-weight: 600; color: #6366f1; text-align: center; margin-top: 0.25rem; }
    .template-preview-shell { border: 1px solid #dbe4f0; border-radius: 16px; background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%); padding: 1rem; margin: 0.5rem 0 1rem 0; }
    .template-preview-title { font-size: 13px; font-weight: 700; color: #1e3a8a; margin-bottom: 0.4rem; }
    .template-preview-subtitle { font-size: 12px; color: #64748b; margin-bottom: 0.75rem; }
    .template-preview-card { border: 1px solid #dbe4f0; border-radius: 14px; background: white; padding: 0.9rem; min-height: 128px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05); }
    .template-preview-card.disabled { opacity: 0.55; border-style: dashed; }
    .template-preview-badge { display: inline-block; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 0.16rem 0.55rem; font-size: 11px; font-weight: 600; margin-right: 0.35rem; }
    .template-preview-badge.off { background: #f3f4f6; color: #6b7280; }
    .template-preview-name { font-size: 16px; font-weight: 700; color: #0f172a; margin: 0.55rem 0 0.3rem 0; }
    .template-preview-desc { font-size: 13px; color: #334155; line-height: 1.5; }
    .template-preview-hint { font-size: 12px; color: #64748b; margin-top: 0.55rem; }
    .template-preview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }
    .template-preview-mini { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; padding: 0.75rem; }
    .template-preview-mini.disabled { opacity: 0.45; }
    .template-preview-mini-name { font-size: 13px; font-weight: 700; color: #0f172a; margin-top: 0.3rem; }
    .template-preview-mini-meta { font-size: 11px; color: #64748b; margin-top: 0.25rem; }
    </style>""",
        unsafe_allow_html=True,
    )


def show_footer():
    if st.session_state.get("_footer_rendered"):
        return
    st.session_state["_footer_rendered"] = True
    st.markdown(
        f"""
    <div class="footer">
        <p><strong>{APP_NAME}</strong></p>
        <p>核心作者: {APP_AUTHOR} · 商业订阅: {APP_COMMERCIAL}</p>
        <p style="margin-top:0.45rem;font-size:10px;color:#94a3b8">© {datetime.now().year} All Rights Reserved.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


# ==================== 初始化 ====================
def init_session():
    s = get_settings()
    if "startup_maintenance_done" not in st.session_state:
        purged_records = cleanup_expired_trashed_records()
        if purged_records:
            st.session_state["startup_maintenance_notice"] = (
                f"系统已按回收站保留策略自动清理 {len(purged_records)} 条过期记录。"
            )
        st.session_state["startup_maintenance_done"] = True
    defaults = {
        "user_compliance_mode": s.get("compliance_mode", "strict"),
        "combo_anchor": None,
        "combo_reqs": [],
        "combo_images": [],
        "combo_generating": False,
        "combo_generation_done": False,
        "combo_results": [],
        "combo_errors": [],
        "combo_titles": [],
        "combo_title_result": {},
        "combo_result_title_language": s.get(
            "default_title_language", DEFAULT_TARGET_LANGUAGE
        ),
        "combo_title_language": s.get(
            "default_title_language", DEFAULT_TARGET_LANGUAGE
        ),
        "combo_image_language": s.get(
            "default_image_language", DEFAULT_TARGET_LANGUAGE
        ),
        "smart_generating": False,
        "smart_generation_done": False,
        "smart_results": [],
        "smart_errors": [],
        "smart_titles": [],
        "smart_title_result": {},
        "smart_result_title_language": s.get(
            "default_title_language", DEFAULT_TARGET_LANGUAGE
        ),
        "smart_title_language": s.get(
            "default_title_language", DEFAULT_TARGET_LANGUAGE
        ),
        "smart_image_language": s.get(
            "default_image_language", DEFAULT_TARGET_LANGUAGE
        ),
        "session_tokens": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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


def show_provider_settings():
    s = get_settings()
    st.markdown(
        '<div class="page-title">⚙️ 提供商设置</div>', unsafe_allow_html=True
    )
    st.markdown(
        "在本地管理 API 提供商信息。支持直连 Gemini 与中转/Relay Base URL，并为后续任务切换提供保护。"
    )

    data = get_providers()
    providers = data.get("providers", [])
    current_id = data.get("current_id")

    current = next((p for p in providers if p.get("id") == current_id), None)
    if current:
        st.info(f"当前提供商: {current.get('name', '')}")

    with st.expander("➕ 添加提供商"):
        new_name = st.text_input("名称", key="prov_new_name")
        new_type = st.selectbox("类型", ["gemini", "relay"], key="prov_new_type")
        new_key = st.text_input("API Key", type="password", key="prov_new_key")
        new_base = st.text_input("Base URL (可选)", key="prov_new_base")
        new_title_model = st.text_input(
            "标题模型 (可选)",
            value=s.get("default_title_model", "gemini-3.1-flash-lite-preview"),
            key="prov_new_title_model",
        )
        new_vision_model = st.text_input(
            "视觉模型 (可选)",
            value=s.get("default_vision_model", "gemini-3.1-flash-lite-preview"),
            key="prov_new_vision_model",
        )
        new_image_model = st.text_input(
            "图像模型 (可选)",
            value=s.get("default_model", "gemini-3.1-flash-image-preview"),
            key="prov_new_image_model",
        )
        if st.button("添加提供商", type="primary"):
            errors = validate_provider_config(new_name, new_type, new_key, new_base)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                new_id = _new_provider_id()
                provider = {
                    "id": new_id,
                    "name": new_name.strip(),
                    "provider_type": new_type,
                    "api_key": new_key.strip(),
                    "base_url": new_base.strip(),
                    "title_model": new_title_model.strip(),
                    "vision_model": new_vision_model.strip(),
                    "image_model": new_image_model.strip(),
                    "enabled": True,
                    "is_default": not providers,
                }
                provider, stored_in_keychain = persist_provider_secret(
                    provider, new_key
                )
                providers.append(provider)
                if not data.get("current_id"):
                    data["current_id"] = new_id
                data["providers"] = providers
                save_providers(data)
                st.success(
                    "✅ 已添加"
                    + ("，Key 已安全保存到 Keychain" if stored_in_keychain else "")
                )
                st.rerun()

    if not providers:
        st.warning("暂无提供商，请先添加。")
        return

    for idx, p in enumerate(providers):
        label = f"{p.get('name', '提供商')} ({p.get('provider_type', 'gemini')})"
        with st.expander(label, expanded=False):
            current_secret = resolve_provider_api_key(p)
            provider_active_tasks = provider_has_active_tasks(p.get("id"))
            provider_is_current = data.get("current_id") == p.get("id")
            p["name"] = st.text_input(
                "名称", p.get("name", ""), key=f"prov_name_{p['id']}"
            )
            p["provider_type"] = st.selectbox(
                "类型",
                ["gemini", "relay"],
                index=["gemini", "relay"].index(p.get("provider_type", "gemini"))
                if p.get("provider_type") in ["gemini", "relay"]
                else 0,
                key=f"prov_type_{p['id']}",
            )
            p["api_key"] = st.text_input(
                "API Key",
                current_secret,
                type="password",
                key=f"prov_key_{p['id']}",
            )
            p["base_url"] = st.text_input(
                "Base URL (可选)", p.get("base_url", ""), key=f"prov_base_{p['id']}"
            )
            p["title_model"] = st.text_input(
                "标题模型 (可选)", p.get("title_model", ""), key=f"prov_title_{p['id']}"
            )
            p["vision_model"] = st.text_input(
                "视觉模型 (可选)",
                p.get("vision_model", ""),
                key=f"prov_vision_{p['id']}",
            )
            p["image_model"] = st.text_input(
                "图像模型 (可选)", p.get("image_model", ""), key=f"prov_image_{p['id']}"
            )
            p["enabled"] = st.checkbox(
                "启用", p.get("enabled", True), key=f"prov_enabled_{p['id']}"
            )
            if provider_active_tasks:
                st.warning("当前有进行中任务正在使用该提供商，暂不允许删除。")
            if provider_is_current:
                st.caption("当前默认提供商")

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("设为当前", key=f"prov_set_{p['id']}"):
                    set_current_provider(p["id"])
                    st.success("✅ 已设为当前")
                    st.rerun()
            with c2:
                if st.button(
                    "测试连接",
                    key=f"prov_test_{p['id']}",
                    disabled=not current_secret,
                ):
                    provider_errors = validate_provider_config(
                        p.get("name", ""),
                        p.get("provider_type", "gemini"),
                        current_secret,
                        p.get("base_url", ""),
                    )
                    if provider_errors:
                        st.error("；".join(provider_errors))
                    else:
                        try:
                            client = GeminiClient(
                                current_secret,
                                base_url=p.get("base_url", ""),
                                title_model=p.get("title_model", ""),
                                vision_model=p.get("vision_model", ""),
                            )
                            resp = client._call(
                                lambda: client.client.models.generate_content(
                                    model=p.get("title_model")
                                    or s.get(
                                        "default_title_model",
                                        "gemini-3.1-flash-lite-preview",
                                    ),
                                    contents=["Return exactly OK."],
                                    config=types.GenerateContentConfig(
                                        response_modalities=["TEXT"]
                                    ),
                                ),
                                timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                            )
                            st.success(f"✅ 连接成功: {(resp.text or '').strip()[:60]}")
                        except Exception as e:
                            st.error(sanitize_task_error(str(e)))
            with c3:
                delete_confirm_key = f"confirm_delete_provider_{p['id']}"
                if st.button(
                    "删除",
                    key=f"prov_del_{p['id']}",
                    disabled=provider_active_tasks,
                ):
                    activate_confirmation(delete_confirm_key)
                    st.rerun()
                replacement = find_replacement_provider(p.get("id"))
                delete_message = "删除后会移除该提供商配置。"
                if provider_is_current:
                    if replacement:
                        delete_message += f" 当前默认将切换为 {replacement.get('name', '其他提供商')}。"
                    else:
                        delete_message += " 删除后当前默认提供商将被清空。"
                if render_confirmation_bar(
                    delete_confirm_key,
                    delete_message,
                    confirm_label="确认删除提供商",
                ):
                    delete_keychain_secret(p.get("keychain_account"))
                    providers.pop(idx)
                    if provider_is_current:
                        data["current_id"] = replacement.get("id", "") if replacement else ""
                    data["providers"] = providers
                    save_providers(data)
                    st.success("✅ 已删除提供商")
                    st.rerun()

    if st.button("💾 保存设置", type="primary"):
        all_errors = []
        for p in providers:
            provider_errors = validate_provider_config(
                p.get("name", ""),
                p.get("provider_type", "gemini"),
                p.get("api_key", ""),
                p.get("base_url", ""),
            )
            if provider_errors:
                all_errors.extend(
                    [f"{p.get('name', '提供商')}: {message}" for message in provider_errors]
                )
                continue
            p, _ = persist_provider_secret(p, p.get("api_key", ""))
        if all_errors:
            for error in all_errors:
                st.error(error)
            return
        data["providers"] = providers
        save_providers(data)
        st.success("✅ 已保存")


def show_settings_center():
    st.markdown('<div class="page-title">🛠️ 系统设置</div>', unsafe_allow_html=True)
    st.markdown(
        "统一管理默认语言、模型、输出目录、代理、自动清理与诊断。模板资产已独立到「模板库」。"
    )

    tabs = st.tabs(["🌐 默认设置", "🩺 诊断", "🛡️ 合规词", "🧠 提示词"])

    with tabs[0]:
        render_settings_defaults_tab()

    with tabs[1]:
        render_settings_diagnostics_tab()

    with tabs[2]:
        st.markdown("### 🛡️ 个人合规词管理")
        show_user_compliance()

        st.markdown("---")
        st.markdown("### 🔒 全局合规黑白名单")
        comp = get_compliance()
        global_blacklist = st.text_area(
            "全局黑名单 (逗号分隔)",
            ", ".join(comp.get("custom_blacklist", [])),
            height=80,
            key="global_comp_blacklist",
        )
        global_whitelist = st.text_area(
            "全局白名单 (逗号分隔)",
            ", ".join(comp.get("whitelist", [])),
            height=80,
            key="global_comp_whitelist",
        )
        if st.button("💾 保存全局合规词", key="save_global_compliance"):
            comp["custom_blacklist"] = [
                w.strip() for w in global_blacklist.split(",") if w.strip()
            ]
            comp["whitelist"] = [
                w.strip() for w in global_whitelist.split(",") if w.strip()
            ]
            save_compliance(comp)
            st.success("✅ 全局合规词已保存")

    with tabs[3]:
        render_prompt_management()


# ==================== 标题生成选项组件 ====================
def render_title_gen_option(prefix: str):
    enabled_templates, template_options, template_names = (
        build_title_template_selector_options(include_custom=False)
    )

    st.markdown("---")
    st.markdown("### 🏷️ 智能标题生成 (可选)")

    enable_title = st.checkbox(
        "📝 同时生成商品标题",
        key=f"{prefix}_enable_title",
        help="勾选后将在出图完成时一并生成英文 + 目标语言标题",
    )

    if enable_title:
        st.markdown('<div class="title-box">', unsafe_allow_html=True)

        target_language = render_target_language_selector(
            prefix,
            "title_language",
            "🌐 标题目标语言",
            "标题默认优先英文；若选择英语，则输出纯英文标题。",
        )
        if target_language == "en":
            st.caption("当前模式: 🇺🇸 纯英文标题")
        else:
            st.caption(
                f"固定首行: 🇺🇸 English · 第二行: {get_title_language_caption(target_language)}"
            )

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

        return enable_title, title_info, selected_template, target_language

    return (
        False,
        "",
        "default",
        st.session_state.get(f"{prefix}_title_language", DEFAULT_TARGET_LANGUAGE),
    )


def display_generated_titles(
    titles: list, prefix: str = "", target_language: str = "zh"
):
    if not titles:
        return

    language_info = get_target_language(target_language)

    if target_language == "en":
        st.markdown("### 🏷️ 生成的商品标题 (纯英文)")
    else:
        st.markdown(f"### 🏷️ 生成的商品标题 (英文 + {language_info['label']})")

    if target_language != "en" and len(titles) >= 6:
        labels = ["🔍 搜索优化", "💰 转化优化", "✨ 差异化"]
        for i in range(0, min(6, len(titles)), 2):
            title_idx = i // 2
            label = labels[title_idx] if title_idx < 3 else f"标题 {title_idx + 1}"
            en_title = titles[i] if i < len(titles) else ""
            localized_title = titles[i + 1] if i + 1 < len(titles) else ""

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
                    <span style="font-size:11px;color:#92400e">{language_info["flag"]} {language_info["label"]}</span><br>
                    <span style="font-size:14px">{localized_title}</span>
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
                f"Title {i // 2 + 1}:\nEN: {titles[i]}\n{language_info['copy_tag']}: {titles[i + 1]}"
                for i in range(0, min(6, len(titles)), 2)
            ]
        )
        if target_language != "en" and len(titles) >= 6
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


def render_title_template_management():
    # Title template editing is kept separate from image template editing so the
    # user-facing settings model stays aligned with product concepts.
    st.markdown("### 🏷️ 标题模板管理")
    title_templates = get_title_templates()
    for key, value in title_templates.items():
        with st.expander(f"{value.get('name', key)}", expanded=False):
            value["name"] = st.text_input(
                "模板名称", value.get("name", ""), key=f"title_tpl_name_{key}"
            )
            value["desc"] = st.text_input(
                "模板说明", value.get("desc", ""), key=f"title_tpl_desc_{key}"
            )
            value["enabled"] = st.checkbox(
                "启用", value.get("enabled", True), key=f"title_tpl_enabled_{key}"
            )
            value["prompt"] = st.text_area(
                "模板提示词",
                value.get("prompt", ""),
                height=220,
                key=f"title_tpl_prompt_{key}",
            )
    if st.button("💾 保存标题模板", key="save_title_templates_btn"):
        save_title_templates(title_templates)
        st.success("✅ 标题模板已保存")


def render_prompt_management():
    st.markdown("### 🧠 提示词管理")
    prompts = get_prompts()
    prompt_keys = list(DEFAULT_PROMPTS.keys())
    selected_prompt = st.selectbox(
        "选择提示词", prompt_keys, key="settings_prompt_key"
    )
    prompts[selected_prompt] = st.text_area(
        f"编辑提示词：{selected_prompt}",
        value=prompts.get(selected_prompt, DEFAULT_PROMPTS[selected_prompt]),
        height=260,
        key=f"prompt_editor_{selected_prompt}",
    )
    if st.button("💾 保存提示词", key="save_prompts_btn"):
        save_prompts(prompts)
        st.success("✅ 提示词已保存")


def render_settings_defaults_tab():
    s = get_settings()
    st.markdown("### 🌐 全局默认")
    c1, c2 = st.columns(2)
    with c1:
        default_title_language = st.selectbox(
            "默认标题语言",
            [item["code"] for item in TARGET_LANGUAGES],
            index=[item["code"] for item in TARGET_LANGUAGES].index(
                s.get("default_title_language", DEFAULT_TARGET_LANGUAGE)
                if s.get("default_title_language", DEFAULT_TARGET_LANGUAGE)
                in [item["code"] for item in TARGET_LANGUAGES]
                else DEFAULT_TARGET_LANGUAGE
            ),
            format_func=format_target_language_option,
            key="settings_default_title_language",
            help="标题页和出图页标题功能默认使用此语言。标题始终优先英文；若选择英语，则输出纯英文标题。",
        )
        default_image_language = st.selectbox(
            "默认图片文案语言",
            [item["code"] for item in TARGET_LANGUAGES],
            index=[item["code"] for item in TARGET_LANGUAGES].index(
                s.get("default_image_language", DEFAULT_TARGET_LANGUAGE)
                if s.get("default_image_language", DEFAULT_TARGET_LANGUAGE)
                in [item["code"] for item in TARGET_LANGUAGES]
                else DEFAULT_TARGET_LANGUAGE
            ),
            format_func=format_target_language_option,
            key="settings_default_image_language",
            help="智能组图和快速出图里的图需、入图文案、图片提示词默认语言。",
        )
        compliance_mode = st.selectbox(
            "默认合规模式",
            [
                k
                for k, v in get_compliance().get("presets", {}).items()
                if v.get("enabled", True)
            ],
            index=[
                k
                for k, v in get_compliance().get("presets", {}).items()
                if v.get("enabled", True)
            ].index(s.get("compliance_mode", "strict"))
            if s.get("compliance_mode", "strict")
            in [
                k
                for k, v in get_compliance().get("presets", {}).items()
                if v.get("enabled", True)
            ]
            else 0,
            format_func=lambda x: (
                get_compliance().get("presets", {}).get(x, {}).get("name", x)
            ),
            key="settings_compliance_mode",
        )
    with c2:
        proxy_mode = st.selectbox(
            "代理模式",
            ["system", "manual", "none"],
            index=["system", "manual", "none"].index(s.get("proxy_mode", "system"))
            if s.get("proxy_mode", "system") in ["system", "manual", "none"]
            else 0,
            format_func=lambda x: {
                "system": "跟随系统",
                "manual": "手动代理",
                "none": "不使用代理",
            }.get(x, x),
            key="settings_proxy_mode",
        )
        proxy_url = st.text_input(
            "手动代理地址",
            value=s.get("proxy_url", "http://127.0.0.1:10808"),
            key="settings_proxy_url",
            help="例如 http://127.0.0.1:10808",
        )
        default_model = st.selectbox(
            "默认出图模型",
            list(MODELS.keys()),
            index=list(MODELS.keys()).index(
                s.get("default_model", "gemini-3.1-flash-image-preview")
            )
            if s.get("default_model", "gemini-3.1-flash-image-preview") in MODELS
            else 0,
            format_func=lambda x: MODELS[x]["name"],
            key="settings_default_model",
        )
        default_title_model = st.text_input(
            "默认标题模型",
            value=s.get("default_title_model", "gemini-3.1-flash-lite-preview"),
            key="settings_default_title_model",
        )
        default_vision_model = st.text_input(
            "默认视觉模型",
            value=s.get("default_vision_model", "gemini-3.1-flash-lite-preview"),
            key="settings_default_vision_model",
        )
        current_output_dir = s.get("project_output_dir", _default_project_output_dir())
        if runtime_supports_output_dir_editing():
            project_output_dir = st.text_input(
                "项目保存目录",
                value=current_output_dir,
                key="settings_project_output_dir",
                help="标题、图片、ZIP 和错误日志都会按项目文件夹保存在这里。",
            )
        else:
            project_output_dir = current_output_dir
            st.text_input(
                "服务器项目目录",
                value=current_output_dir,
                disabled=True,
                key="settings_project_output_dir_server",
                help="服务器版默认把项目保存在服务器项目中心，用户通过浏览器下载结果。",
            )
            st.caption(
                "当前运行模式不会直接操作访问者电脑上的文件夹。结果会先进入服务器项目中心，再由用户下载。"
            )
        trash_retention_days = st.number_input(
            "回收站保留天数",
            min_value=0,
            step=1,
            value=int(s.get("trash_retention_days", 15)),
            key="settings_trash_retention_days",
            help="0 表示不自动清理；该值将用于后续回收站自动清理策略。",
        )
    if st.button("💾 保存全局默认", type="primary", key="save_global_defaults"):
        s["default_title_language"] = default_title_language
        s["default_image_language"] = default_image_language
        s["compliance_mode"] = compliance_mode
        s["default_model"] = default_model
        s["default_title_model"] = default_title_model.strip()
        s["default_vision_model"] = default_vision_model.strip()
        s["project_output_dir"] = project_output_dir.strip()
        s["trash_retention_days"] = int(trash_retention_days)
        s["proxy_mode"] = proxy_mode
        s["proxy_url"] = proxy_url.strip()
        save_settings(s)
        apply_proxy_settings(s)
        st.session_state.user_compliance_mode = compliance_mode
        st.success("✅ 全局默认已保存")

    if st.button("🌐 测试 Gemini 连接", key="test_proxy_connectivity"):
        apply_proxy_settings(s)
        provider = get_active_provider()
        if not provider or not provider.get("api_key"):
            st.warning("请先配置可用 Provider/K。")
        else:
            try:
                client = GeminiClient(
                    provider.get("api_key"),
                    base_url=provider.get("base_url", ""),
                    title_model=provider.get("title_model", ""),
                    vision_model=provider.get("vision_model", ""),
                )
                resp = client._call(
                    lambda: client.client.models.generate_content(
                        model=provider.get("title_model")
                        or s.get(
                            "default_title_model", "gemini-3.1-flash-lite-preview"
                        ),
                        contents=["Return exactly OK."],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT"]
                        ),
                    ),
                    timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
                )
                st.success(f"✅ 连接成功: {(resp.text or '').strip()[:60]}")
            except Exception as e:
                msg = str(e)
                if (
                    "FAILED_PRECONDITION" in msg
                    or "User location is not supported" in msg
                ):
                    st.warning(
                        "✅ 已连通 Google，但当前账号或地区不支持该 API 调用。请切换可用的账号、项目或代理出口。"
                    )
                else:
                    st.error(f"连接失败: {sanitize_task_error(msg)}")


def render_settings_diagnostics_tab():
    records = list_history_records()
    diagnostics = collect_diagnostics(records)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("历史记录", diagnostics["record_count"])
    d2.metric("manifest", diagnostics["manifest_count"])
    d3.metric("缺失文件项目", diagnostics["missing_record_count"])
    d4.metric("孤儿目录", diagnostics["orphan_dir_count"])

    st.caption(f"当前提供商: {diagnostics['provider_name']}")
    st.caption(f"进行中任务: {diagnostics['active_task_count']}")
    st.caption(f"项目输出目录: {diagnostics['output_dir']}")

    button_count = 2 if runtime_supports_local_file_access() else 1
    columns = st.columns(button_count)
    c1 = columns[0]
    with c1:
        if st.button("🛠️ 重建历史索引", key="settings_rebuild_history_index"):
            rebuilt_records = rebuild_history_index_from_manifests()
            st.success(f"已重建 {len(rebuilt_records)} 条历史记录。")
            st.rerun()
    if runtime_supports_local_file_access():
        with columns[1]:
            if st.button("📂 打开输出目录", key="settings_open_output_dir"):
                if open_in_file_manager(diagnostics["output_dir"]):
                    st.success("已打开输出目录。")
                else:
                    st.error("无法打开输出目录。")
    else:
        st.caption("服务器版不提供“打开本地文件夹”，请在项目中心下载或清理服务器结果。")

    if diagnostics["missing_records"]:
        st.warning("检测到部分历史项目存在缺失文件。建议前往项目中心 > 文件管理进行修复。")
    if diagnostics["orphan_dirs"]:
        st.warning("检测到输出目录中存在未收录的孤儿目录。可在文件管理中检查或清理。")


def show_template_library():
    st.markdown('<div class="page-title">🧩 模板库</div>', unsafe_allow_html=True)
    st.markdown(
        "统一管理标题模板与图片模板资产。业务页面只负责选择并使用模板，模板资产统一在这里维护。"
    )

    diagnostics = collect_template_library_diagnostics()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("标题模板", diagnostics["title_template_count"])
    d2.metric("启用标题模板", diagnostics["enabled_title_template_count"])
    d3.metric("图片模板", diagnostics["image_template_count"])
    d4.metric("启用翻译模板", diagnostics["enabled_translation_count"])

    if diagnostics["issues"]:
        st.warning("模板库健康检查发现潜在问题。建议修正后再交给业务页面使用。")
        for issue in diagnostics["issues"][:8]:
            st.caption(f"• {issue}")
    else:
        st.success("模板库健康检查通过。当前模板结构与关键占位符完整。")

    tabs = st.tabs(["🏷️ 标题模板", "🖼️ 图片模板"])

    with tabs[0]:
        render_title_template_management()

    with tabs[1]:
        render_image_template_management()


def render_image_template_management():
    # Image template management intentionally renders from workflow groups instead
    # of raw storage keys, so the UI can stay business-oriented while storage
    # remains backward-compatible.
    st.markdown("### 🧩 图片模板管理")
    st.caption(
        "按业务工作流管理图片模板。先看模板影响哪个页面，再决定是否启用、排序或修改名称说明。"
    )
    templates = get_templates()
    st.info("当前模板页已支持真实模板管理与第一版所见即所得预览。")

    for group_key in TEMPLATE_GROUP_ORDER:
        group_meta = TEMPLATE_PAGE_META.get(group_key, {})
        st.markdown(f"#### {group_meta.get('title', group_key)}")
        st.caption(group_meta.get("desc", ""))
        group = templates.get(group_key, {})
        render_template_group_preview(group_key, group_meta, group)
        sorted_items = get_sorted_templates(group_key, enabled_only=False)
        for item_key, item in sorted_items:
            item_meta = TEMPLATE_ITEM_META.get(group_key, {}).get(item_key, {})
            with st.expander(
                f"{item.get('icon', '📦')} {item.get('name', item_key)}",
                expanded=False,
            ):
                c1, c2 = st.columns([1.1, 1])
                with c1:
                    st.caption(
                        f"适用页面: {group_meta.get('page_label', '未定义')} · 用途: {item_meta.get('usage_note', item.get('desc', ''))}"
                    )
                    item["name"] = st.text_input(
                        "模板名称",
                        item.get("name", item_meta.get("recommended_name", "")),
                        key=f"tpl_name_{group_key}_{item_key}",
                        help="建议使用业务人员能一眼看懂的名称。",
                    )
                    item["desc"] = st.text_input(
                        "模板说明",
                        item.get("desc", item_meta.get("recommended_desc", "")),
                        key=f"tpl_desc_{group_key}_{item_key}",
                        help="建议直接写清这个模板会生成什么类型的图。",
                    )
                    if item_meta.get("usage_note"):
                        st.caption(f"用途提示: {item_meta.get('usage_note')}")
                    if "hint" in item:
                        item["hint"] = st.text_input(
                            "提示语 / Hint",
                            item.get("hint", ""),
                            key=f"tpl_hint_{group_key}_{item_key}",
                            help="供系统内部生成时参考的英文或说明性提示。",
                        )
                    if "prompt" in item:
                        item["prompt"] = st.text_area(
                            "模板 Prompt",
                            item.get("prompt", ""),
                            height=220,
                            key=f"tpl_prompt_{group_key}_{item_key}",
                            help="该模板会直接影响翻译保版模式下的实际生成提示词。",
                        )
                    item["enabled"] = st.checkbox(
                        "启用",
                        item.get("enabled", True),
                        key=f"tpl_enabled_{group_key}_{item_key}",
                    )
                    item["order"] = st.number_input(
                        "排序",
                        min_value=1,
                        step=1,
                        value=int(item.get("order", 1)),
                        key=f"tpl_order_{group_key}_{item_key}",
                    )
                with c2:
                    render_template_item_preview(item, group_meta, item_meta)

        st.markdown("---")
    if st.button("💾 保存图片模板", key="save_templates_btn"):
        save_templates(templates)
        st.success("✅ 图片模板已保存")


# ==================== Gemini 3 高级设置 ====================
def render_gemini3_settings(prefix: str, model_key: str):
    model_info = MODELS.get(
        model_key,
        {
            "name": model_key,
            "resolutions": ["1K"],
            "max_refs": 3,
            "thinking_levels": [],
            "default_thinking": None,
            "supports_thinking": False,
        },
    )
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

    thinking_level = "high"  # 默认值

    if supports_thinking:
        with c3:
            thinking_levels = model_info.get("thinking_levels", ["low", "high"])
            default_thinking = model_info.get("default_thinking", "high")
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
                help="仅 Nano Banana Pro 支持此功能",
            )
    else:
        # Flash模型不支持thinking_level，显示提示
        st.caption("💡 Nano Banana Flash 不支持推理深度调节")

    return aspect, size, thinking_level


# ==================== 结果显示组件 ====================
def display_generation_results(
    results: list,
    errors: list,
    titles: list,
    tokens_used: int,
    prefix: str,
    target_language: str = "zh",
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
        zip_bytes = create_zip_from_results(results, titles, target_language)

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
        display_generated_titles(titles, prefix, target_language)


def build_smart_requirements(selected_types: dict, templates: dict) -> list:
    requirements = []
    for tk, cnt in selected_types.items():
        info = templates.get(tk, {})
        for idx in range(cnt):
            requirements.append(
                {
                    "type_key": tk,
                    "type_name": info.get("name", tk),
                    "index": idx + 1,
                    "topic": info.get("name", tk),
                    "scene": info.get("desc", ""),
                    "copy": info.get("desc", ""),
                }
            )
    return requirements


def _save_uploaded_images(files, prefix: str):
    saved = []
    upload_dir = DATA_DIR / "task_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for idx, f in enumerate(files or []):
        try:
            img = (
                f.copy().convert("RGB")
                if isinstance(f, Image.Image)
                else Image.open(f).convert("RGB")
            )
            filename = f"{prefix}_{idx + 1}.png"
            path = upload_dir / filename
            img.save(path, format="PNG")
            saved.append(str(path))
        except Exception:
            continue
    return saved


def _execute_title_task(task: dict):
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    client = GeminiClient(
        provider.get("api_key"),
        base_url=provider.get("base_url", ""),
        title_model=provider.get("title_model", ""),
        vision_model=provider.get("vision_model", ""),
    )
    images = load_image_paths(payload.get("image_paths", []))
    if images:
        result = client.generate_titles_from_image(
            images,
            payload.get("product_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
    else:
        result = client.generate_titles(
            payload.get("product_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
    if not result.get("success"):
        raise Exception(format_title_error(result))
    return {
        "titles": result.get("titles", []),
        "errors": [],
        "files": [],
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def _execute_smart_task(task: dict):
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    images = load_image_paths(payload.get("image_paths", []))
    if not images:
        raise Exception("任务图片已丢失，请重新上传")
    templates = get_template_group("smart_types")
    client = GeminiClient(
        provider.get("api_key"),
        payload.get("model", provider.get("image_model", "")),
        base_url=provider.get("base_url", ""),
        title_model=provider.get("title_model", ""),
        vision_model=provider.get("vision_model", ""),
    )
    anchor = client.analyze_product(
        images, payload.get("name", ""), payload.get("material", "")
    )
    selected_types = payload.get("selected_types", {})
    image_language = payload.get("image_language", DEFAULT_TARGET_LANGUAGE)
    requirements = build_smart_requirements(selected_types, templates)
    requirements = client.generate_en_copy(anchor, requirements, image_language)
    req_map = {(req.get("type_key"), req.get("index")): req for req in requirements}
    results = []
    errors = []
    done = 0
    total = sum(selected_types.values())
    for tk, cnt in selected_types.items():
        info = templates[tk]
        for idx in range(cnt):
            ensure_task_not_cancelled(task["id"])
            done += 1
            update_task(task["id"], progress={"done": done, "total": total})
            req = req_map.get(
                (tk, idx + 1),
                {
                    "type_key": tk,
                    "type_name": info["name"],
                    "index": idx + 1,
                    "topic": info.get("name", tk),
                    "scene": info.get("desc", ""),
                },
            )
            prompt = client.compose_image_prompt(
                anchor, req, payload.get("aspect", "1:1"), image_language
            )
            try:
                img = client.generate_image(
                    images,
                    prompt,
                    payload.get("aspect", "1:1"),
                    payload.get("size", "1K"),
                    payload.get("thinking_level", "high"),
                    image_language,
                )
            except Exception as e:
                client.last_error = str(e)
                img = None
            if img:
                filename = f"{task['id']}_{str(done).zfill(2)}_{info['name']}.png"
                results.append(persist_image_for_task(img, filename))
            else:
                errors.append(client.get_last_error() or f"{info['name']} 生成失败")
    titles = []
    if payload.get("enable_title") and payload.get("title_info"):
        title_result = client.generate_titles(
            payload.get("title_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
        if title_result.get("success"):
            titles = title_result.get("titles", [])
        else:
            errors.append(format_title_error(title_result))
    if not results and errors:
        raise Exception(errors[0])
    return {
        "titles": titles,
        "errors": errors,
        "files": results,
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def _execute_translate_task(task: dict):
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    images = load_image_paths(payload.get("image_paths", []))
    if not images:
        raise Exception("任务图片已丢失，请重新上传")
    client = GeminiClient(
        provider.get("api_key"),
        payload.get("model", provider.get("image_model", "")),
        base_url=provider.get("base_url", ""),
        title_model=provider.get("title_model", ""),
        vision_model=provider.get("vision_model", ""),
    )
    image_language = payload.get("image_language", DEFAULT_TARGET_LANGUAGE)
    compliance_mode = payload.get("compliance_mode", "strict")
    prompt = build_translation_prompt(
        image_language,
        payload.get("aspect", "1:1"),
        compliance_mode,
        payload.get("translation_template", "preserve_layout"),
    )
    results = []
    errors = []
    total = len(images)
    for idx, image in enumerate(images):
        ensure_task_not_cancelled(task["id"])
        update_task(task["id"], progress={"done": idx + 1, "total": total})
        try:
            translated = client.generate_image(
                [image],
                prompt,
                payload.get("aspect", "1:1"),
                payload.get("size", "1K"),
                payload.get("thinking_level", "high"),
                image_language,
            )
        except Exception as e:
            client.last_error = str(e)
            translated = None
        if translated:
            filename = f"{task['id']}_{str(idx + 1).zfill(2)}_translated.png"
            results.append(persist_image_for_task(translated, filename))
        else:
            errors.append(client.get_last_error() or f"第{idx + 1}张翻译失败")
    if not results and errors:
        raise Exception(errors[0])
    return {
        "titles": [],
        "errors": errors,
        "files": results,
        "target_language": image_language,
    }


def _execute_combo_task(task: dict):
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    refs = load_image_paths(payload.get("image_paths", []))
    if not refs:
        raise Exception("任务参考图已丢失，请重新上传")
    reqs = payload.get("reqs", [])
    anchor = payload.get("anchor", {})
    client = GeminiClient(
        provider.get("api_key"),
        payload.get("model", provider.get("image_model", "")),
        base_url=provider.get("base_url", ""),
        title_model=provider.get("title_model", ""),
        vision_model=provider.get("vision_model", ""),
    )
    results = []
    errors = []
    total = len(reqs)
    for i, req in enumerate(reqs):
        ensure_task_not_cancelled(task["id"])
        update_task(task["id"], progress={"done": i + 1, "total": total})
        prompt = client.compose_image_prompt(
            anchor,
            req,
            payload.get("aspect", "1:1"),
            payload.get("image_language", DEFAULT_TARGET_LANGUAGE),
        )
        try:
            img = client.generate_image(
                refs,
                prompt,
                payload.get("aspect", "1:1"),
                payload.get("size", "1K"),
                payload.get("thinking_level", "high"),
                payload.get("image_language", DEFAULT_TARGET_LANGUAGE),
            )
        except Exception as e:
            client.last_error = str(e)
            img = None
        if img:
            filename = f"{task['id']}_{str(i + 1).zfill(2)}_{req.get('type_name', 'image')}.png"
            results.append(persist_image_for_task(img, filename))
        else:
            errors.append(
                client.get_last_error() or f"{req.get('type_name', '图片')} 生成失败"
            )
    titles = []
    if payload.get("enable_title") and payload.get("title_info"):
        title_result = client.generate_titles(
            payload.get("title_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
        if title_result.get("success"):
            titles = title_result.get("titles", [])
        else:
            errors.append(format_title_error(title_result))
    if not results and errors:
        raise Exception(errors[0])
    return {
        "titles": titles,
        "errors": errors,
        "files": results,
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def run_task_worker(task_id: str):
    task_threads = get_task_threads()
    task = next((t for t in list_tasks() if t.get("id") == task_id), None)
    if not task or task.get("status") != "queued":
        return
    update_task(task_id, status="running")
    try:
        ensure_task_not_cancelled(task_id)
        if task.get("type") == "title":
            result = _execute_title_task(task)
        elif task.get("type") == "translate":
            result = _execute_translate_task(task)
        elif task.get("type") == "smart":
            result = _execute_smart_task(task)
        else:
            result = _execute_combo_task(task)
        if is_task_cancelled(task_id):
            return
        completed_task = update_task(
            task_id,
            status="done",
            titles=result.get("titles", []),
            errors=result.get("errors", []),
            result_files=result.get("files", []),
            result_title_language=result.get(
                "target_language", DEFAULT_TARGET_LANGUAGE
            ),
        )
        record_task_history(completed_task or task, result)
    except Exception as e:
        if is_task_cancelled(task_id):
            return
        failed_task = update_task(
            task_id, status="error", errors=[sanitize_task_error(str(e))]
        )
        record_task_history(
            failed_task or task,
            {
                "titles": [],
                "errors": [sanitize_task_error(str(e))],
                "files": [],
                "target_language": task.get(
                    "result_title_language", DEFAULT_TARGET_LANGUAGE
                ),
            },
        )
    finally:
        task_threads.pop(task_id, None)
        schedule_task_workers()


def schedule_task_workers():
    normalize_running_tasks()
    task_threads = get_task_threads()
    running_threads = {tid: th for tid, th in task_threads.items() if th.is_alive()}
    task_threads.clear()
    task_threads.update(running_threads)
    available = MAX_ACTIVE_TASKS - len(task_threads)
    if available <= 0:
        return
    for task in sorted(list_tasks(), key=lambda x: x.get("created_at", "")):
        if available <= 0:
            break
        if task.get("status") != "queued":
            continue
        th = threading.Thread(
            target=run_task_worker, args=(task.get("id"),), daemon=True
        )
        task_threads[task.get("id")] = th
        th.start()
        available -= 1


def render_task_center():
    tasks = list_tasks()
    records = list_active_history_records()
    trashed_records = list_trashed_history_records()
    st.markdown("#### 📚 项目中心概览")
    if not tasks and not records and not trashed_records:
        st.caption("暂无项目")
        return
    active = [t for t in tasks if t.get("status") in {"queued", "running"}]
    completed_records = [r for r in records if r.get("status") == "done"]
    st.caption(
        f"进行中 {len(active)} · 历史 {len(records)} · 回收站 {len(trashed_records)}"
    )
    if active:
        for task in active[:3]:
            total = task.get("progress", {}).get("total", 0)
            done = task.get("progress", {}).get("done", 0)
            st.caption(
                f"• {task.get('summary', task.get('type', 'task'))} · {done}/{total}"
            )
    elif completed_records:
        st.caption(f"最近已完成项目 {len(completed_records)} 个")
    else:
        st.caption("暂无进行中的任务")


def set_nav_page(page: str):
    st.session_state["nav_page"] = page


def get_nav_page():
    current = st.session_state.get("nav_page", MAIN_NAV_ITEMS[0])
    if current == "🎨 快速出图":
        current = "🎨 快速出图 / 图片翻译"
    allowed = set(MAIN_NAV_ITEMS + MANAGEMENT_NAV_ITEMS + [PROJECT_CENTER_PAGE])
    if current not in allowed:
        current = MAIN_NAV_ITEMS[0]
    st.session_state["nav_page"] = current
    return current


def render_sidebar_nav_section(title: str, items: list, current_page: str):
    st.markdown(f"#### {title}")
    next_page = current_page
    for item in items:
        button_type = "primary" if item == current_page else "secondary"
        if st.button(item, key=f"nav_{title}_{item}", use_container_width=True, type=button_type):
            next_page = item
    return next_page


def render_status_center_content():
    tasks = list_tasks()
    active_tasks = [task for task in tasks if task.get("status") in {"queued", "running"}]
    active_records = list_active_history_records()
    recent_done = [record for record in active_records if record.get("status") == "done"][:3]
    recent_error = [record for record in active_records if record.get("status") == "error"][:3]

    st.caption(f"进行中 {len(active_tasks)} · 历史 {len(active_records)} · 回收站 {len(list_trashed_history_records())}")
    if active_tasks:
        st.markdown("**进行中任务**")
        for task in active_tasks[:4]:
            progress = task.get("progress", {}) or {}
            st.caption(
                f"• {task.get('summary', task.get('type', 'task'))} · {progress.get('done', 0)}/{progress.get('total', 0)}"
            )
    else:
        st.caption("当前没有进行中的任务。")

    if recent_done:
        st.markdown("**最近完成**")
        for record in recent_done:
            st.caption(f"• {record.get('summary', record.get('task_type', '任务'))}")

    if recent_error:
        st.markdown("**最近失败**")
        for record in recent_error:
            st.caption(f"• {record.get('summary', record.get('task_type', '任务'))}")

    if st.button("打开完整项目中心", key="status_center_open_project", use_container_width=True):
        set_nav_page(PROJECT_CENTER_PAGE)
        st.rerun()


def render_global_toolbar(current_page: str):
    left, mid, right = st.columns([6, 1.4, 1.6])
    with left:
        page_label = current_page if current_page != PROJECT_CENTER_PAGE else "📡 状态中心 / 项目中心"
        st.caption(f"当前区域: {page_label}")
    with mid:
        if hasattr(st, "popover"):
            with st.popover("📡 状态中心", use_container_width=True):
                render_status_center_content()
        elif st.button("📡 状态中心", key="status_center_fallback", use_container_width=True):
            set_nav_page(PROJECT_CENTER_PAGE)
            st.rerun()
    with right:
        if st.button("📚 项目中心", key="toolbar_project_center", use_container_width=True):
            set_nav_page(PROJECT_CENTER_PAGE)
            st.rerun()


def _record_status_label(status: str):
    return {
        "done": "🟢 已完成",
        "error": "🔴 失败",
        "cancelled": "⚫ 已取消",
        "expired": "🟠 已过期",
    }.get(status, status or "unknown")


def _task_status_label(status: str):
    return {
        "queued": "🟡 排队中",
        "running": "🔵 执行中",
        "done": "🟢 已完成",
        "error": "🔴 失败",
        "cancelled": "⚫ 已取消",
        "expired": "🟠 已过期",
    }.get(status, status or "unknown")


def render_history_record_block(record: dict, in_trash: bool = False):
    title = record.get("summary") or record.get("task_type", "任务")
    completed_at = record.get("completed_at") or record.get("created_at", "")
    target_language = record.get("target_language", DEFAULT_TARGET_LANGUAGE)
    zip_path = record.get("zip_path", "")
    artifact_dir = record.get("artifact_dir", "")
    files = record.get("file_paths", []) or []
    titles = record.get("titles", []) or []
    file_summary = summarize_record_files(record)
    state_label = "🗑️ 回收站" if in_trash else _record_status_label(record.get("status"))

    with st.expander(
        f"{state_label} · {title} · {len(files)} 文件 · {completed_at}",
        expanded=False,
    ):
        st.caption(f"任务ID: {record.get('task_id', '')}")
        st.caption(
            f"项目文件夹: {record.get('project_name', Path(artifact_dir).name if artifact_dir else '')}"
        )
        st.caption(f"语言: {get_target_language(target_language)['label']}")
        st.caption(
            f"磁盘占用: {format_bytes(file_summary['size_bytes'])} · 输入素材 {file_summary['input_count']} 个"
        )
        if artifact_dir:
            st.caption(
                f"{'本地项目目录' if DESKTOP_MODE else '服务器项目目录'}: {artifact_dir}"
            )
        if file_summary["missing_count"]:
            st.warning(f"检测到 {file_summary['missing_count']} 个文件缺失，建议到文件管理页检查。")
        if record.get("errors"):
            st.warning("; ".join(record.get("errors", [])[:3]))

        if zip_path and Path(zip_path).exists() and not in_trash:
            try:
                zip_bytes = Path(zip_path).read_bytes()
                st.download_button(
                    "⬇️ 下载本地 ZIP",
                    data=zip_bytes,
                    file_name=Path(zip_path).name,
                    mime="application/zip",
                    key=f"hist_zip_{record.get('task_id')}",
                )
            except Exception:
                st.caption("ZIP 文件暂时不可读取")

        if in_trash:
            column_weights = [1, 1, 1] if runtime_supports_local_file_access() else [1, 1]
            columns = st.columns(column_weights)
            restore_key = f"restore_hist_{record.get('task_id')}"
            purge_key = f"purge_hist_{record.get('task_id')}"
            with columns[0]:
                if st.button("♻️ 恢复", key=f"{restore_key}_trigger"):
                    restored = restore_history_record(record.get("task_id"))
                    if restored:
                        st.success("已恢复到历史项目")
                        st.rerun()
            if runtime_supports_local_file_access():
                with columns[1]:
                    if st.button("📂 打开文件夹", key=f"trash_open_{record.get('task_id')}"):
                        if open_record_output(record):
                            st.success("已打开文件夹")
                        else:
                            st.error("无法打开文件夹")
                purge_col = columns[2]
            else:
                purge_col = columns[1]
            with purge_col:
                if st.button("🧨 彻底删除", key=f"{purge_key}_trigger"):
                    activate_confirmation(purge_key)
                    st.rerun()
            if render_confirmation_bar(
                purge_key,
                "彻底删除会移除该记录及其本地文件，执行后不可恢复。",
                confirm_label="确认彻底删除",
            ):
                purged_record = purge_trashed_history_record(record.get("task_id"))
                if purged_record:
                    st.success("已彻底删除")
                    st.rerun()
        else:
            if runtime_supports_local_file_access():
                c1, c2, c3, c4 = st.columns(4)
            else:
                c1, c2, c3 = st.columns(3)
            trash_key = f"trash_hist_{record.get('task_id')}"
            action_col = c1
            relaunch_col = c2 if runtime_supports_local_file_access() else c1
            trash_col = c3 if runtime_supports_local_file_access() else c2
            summary_col = c4 if runtime_supports_local_file_access() else c3
            if runtime_supports_local_file_access():
                with action_col:
                    if st.button("📂 打开文件夹", key=f"hist_open_{record.get('task_id')}"):
                        if open_record_output(record):
                            st.success("已打开文件夹")
                        else:
                            st.error("无法打开文件夹")
            with relaunch_col:
                if st.button("🔄 重新发起", key=f"hist_relaunch_{record.get('task_id')}"):
                    relaunched_task, relaunch_err = relaunch_history_record(
                        record.get("task_id")
                    )
                    if relaunched_task:
                        st.success(f"已重新发起：{relaunched_task.get('id')}")
                        st.rerun()
                    else:
                        st.error(relaunch_err or "重新发起失败")
            with trash_col:
                if st.button("🗑️ 删除到回收站", key=f"{trash_key}_trigger"):
                    activate_confirmation(trash_key)
                    st.rerun()
            with summary_col:
                st.caption(f"共 {len(files)} 个结果文件")
            if render_confirmation_bar(
                trash_key,
                "删除后会进入回收站，可在回收站恢复；本地文件会先保留。",
                confirm_label="确认移入回收站",
            ):
                trashed = trash_history_record(record.get("task_id"))
                if trashed:
                    st.success("已移入回收站")
                    st.rerun()

        if record.get("input_file_paths"):
            st.caption(f"可重发素材: {len(record.get('input_file_paths', []))} 个")

        if files:
            preview_cols = st.columns(min(4, len(files)))
            for idx, file_path in enumerate(files[:4]):
                p = Path(file_path)
                if p.exists():
                    with preview_cols[idx % len(preview_cols)]:
                        try:
                            st.image(
                                Image.open(p),
                                caption=p.name,
                                use_container_width=True,
                            )
                        except Exception:
                            st.caption(p.name)

        if titles:
            st.markdown("##### 标题内容")
            st.code("\n".join(titles), language="text")


def render_file_management_tab(records: list):
    if startup_notice := st.session_state.pop("startup_maintenance_notice", ""):
        st.success(startup_notice)
    if not records:
        st.info("暂无可管理的项目文件。")
    orphan_dirs = find_orphan_project_dirs(records)
    total_size = sum(summarize_record_files(record)["size_bytes"] for record in records)
    missing_records = [
        record for record in records if summarize_record_files(record)["missing_count"]
    ]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("项目数", len(records))
    c2.metric("总占用", format_bytes(total_size))
    c3.metric("异常项目", len(missing_records))
    c4.metric("孤儿目录", len(orphan_dirs))

    t1, t2 = st.columns(2)
    with t1:
        if st.button("🛠️ 从 manifest 重建历史索引", key="rebuild_history_index"):
            rebuilt_records = rebuild_history_index_from_manifests()
            st.success(f"已从项目目录重建 {len(rebuilt_records)} 条历史记录。")
            st.rerun()
    with t2:
        st.caption("当 `history.json` 丢失或不完整时，可以用项目目录里的 manifest 重新生成索引。")

    if orphan_dirs:
        st.warning("检测到未被历史索引收录的项目目录。你可以先打开检查，再执行索引重建。")
        for orphan in orphan_dirs:
            orphan_delete_key = f"confirm_delete_orphan_{orphan['path']}"
            with st.expander(
                f"孤儿目录 · {orphan['name']} · {format_bytes(orphan['size_bytes'])} · {orphan['file_count']} 个文件",
                expanded=False,
            ):
                st.caption(orphan["path"])
                st.caption(
                    "包含 manifest，可通过索引重建恢复"
                    if orphan["has_manifest"]
                    else "不包含 manifest，建议手动检查后决定是否保留"
                )
                if runtime_supports_local_file_access():
                    if st.button(
                        "📂 打开孤儿目录", key=f"open_orphan_{orphan['path']}"
                    ):
                        if open_in_file_manager(orphan["path"]):
                            st.success("已打开目录")
                        else:
                            st.error("无法打开目录")
                if not orphan["has_manifest"]:
                    if st.button(
                        "🧨 删除孤儿目录",
                        key=f"delete_orphan_trigger_{orphan['path']}",
                    ):
                        activate_confirmation(orphan_delete_key)
                        st.rerun()
                    if render_confirmation_bar(
                        orphan_delete_key,
                        "该目录未被历史索引管理，也不包含 manifest。确认后会直接删除整个目录。",
                        confirm_label="确认删除孤儿目录",
                    ):
                        if delete_orphan_project_dir(orphan["path"]):
                            st.success("已删除孤儿目录")
                            st.rerun()
                        st.error("删除失败，请检查目录权限。")

    for record in records:
        summary = summarize_record_files(record)
        title = record.get("summary") or record.get("task_type", "任务")
        rebuild_zip_key = f"rebuild_zip_{record.get('task_id')}"
        with st.expander(
            f"{title} · {format_bytes(summary['size_bytes'])} · 缺失 {summary['missing_count']} 个文件",
            expanded=False,
        ):
            st.caption(f"目录: {record.get('artifact_dir', '')}")
            st.caption(
                f"结果文件 {summary['file_count']} 个 · 输入素材 {summary['input_count']} 个"
            )
            if summary["missing_count"]:
                st.warning("检测到记录与文件不一致，可打开目录检查，或先尝试从 manifest 重建历史索引。")
                for missing_path in summary["missing_paths"][:5]:
                    st.code(missing_path, language="text")
            if runtime_supports_local_file_access():
                if st.button(
                    "📂 打开项目目录", key=f"file_mgmt_open_{record.get('task_id')}"
                ):
                    if open_record_output(record):
                        st.success("已打开项目目录")
                    else:
                        st.error("无法打开项目目录")
            zip_exists = bool(record.get("zip_path")) and Path(record.get("zip_path")).exists()
            if st.button(
                "♻️ 重建 ZIP" if not zip_exists else "🔁 重新生成 ZIP",
                key=f"{rebuild_zip_key}_trigger",
            ):
                rebuilt_record, rebuild_err = rebuild_record_zip(record.get("task_id"))
                if rebuilt_record:
                    st.success("ZIP 已重建完成。")
                    st.rerun()
                st.error(rebuild_err or "ZIP 重建失败。")
            if not zip_exists:
                st.caption("当前 ZIP 缺失，建议先重建后再下载或归档。")


def show_project_center():
    st.markdown('<div class="page-title">📚 项目中心</div>', unsafe_allow_html=True)
    st.markdown(
        "统一管理进行中任务、历史项目、回收站和项目文件。服务器版结果会先保存在项目中心，再由用户下载。"
        if SERVER_MODE
        else "统一管理进行中任务、历史项目、回收站和本地文件。"
    )

    tasks = list_tasks()
    active_records = list_active_history_records()
    trashed_records = list_trashed_history_records()
    active_tasks = [t for t in tasks if t.get("status") in {"queued", "running"}]
    completed_records = [r for r in active_records if r.get("status") == "done"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("进行中", len(active_tasks))
    m2.metric("历史项目", len(active_records))
    m3.metric("回收站", len(trashed_records))
    m4.metric("已完成", len(completed_records))

    tab_running, tab_history, tab_trash, tab_files = st.tabs(
        ["🚧 进行中", "🗂️ 历史项目", "🗑️ 回收站", "🧾 文件管理"]
    )

    with tab_running:
        if not active_tasks:
            st.info("当前没有进行中的任务。新的生成任务会出现在这里。")
        for task in active_tasks:
            total = task.get("progress", {}).get("total", 0)
            done = task.get("progress", {}).get("done", 0)
            provider = get_provider_by_id((task.get("payload", {}) or {}).get("provider_id", ""))
            with st.expander(
                f"{_task_status_label(task.get('status'))} · {task.get('summary', task.get('type', 'task'))} · {done}/{total}",
                expanded=False,
            ):
                st.caption(f"任务ID: {task.get('id', '')}")
                if provider:
                    st.caption(f"使用提供商: {provider.get('name', '')}")
                if task.get("errors"):
                    st.warning("; ".join(task.get("errors", [])[:3]))
                if st.button(
                    f"取消任务 {task.get('id')}", key=f"project_cancel_{task.get('id')}"
                ):
                    cancel_task(task.get("id"))
                    st.success("已取消任务")
                    st.rerun()

    with tab_history:
        if completed_records:
            clear_done_key = "confirm_clear_done_history"
            st.caption("只会清理已完成项目，失败/取消/过期记录会保留。")
            if st.button(
                "🧹 清理已完成项目",
                key="history_clear_done_trigger",
                help="清理后会先进入回收站，本地文件暂不直接删除。",
            ):
                activate_confirmation(clear_done_key)
                st.rerun()
            if render_confirmation_bar(
                clear_done_key,
                f"将把 {len(completed_records)} 条已完成项目移入回收站，失败和取消项目不会受影响。",
                confirm_label="确认清理",
            ):
                removed_tasks = clear_terminal_tasks()
                moved_records = len(trash_history_records_by_status({"done"}))
                st.session_state["project_center_notice"] = (
                    f"已清理 {removed_tasks} 条队列记录，并将 {moved_records} 条已完成项目移入回收站。"
                )
                st.rerun()
        if notice := st.session_state.pop("project_center_notice", ""):
            st.success(notice)
        if not active_records:
            st.info("暂无历史项目。任务完成或失败后会自动出现在这里。")
        else:
            render_batch_record_actions(active_records, mode="history")
        for record in active_records:
            render_history_record_block(record, in_trash=False)

    with tab_trash:
        retention_days = int(get_settings().get("trash_retention_days", 15) or 0)
        if trashed_records:
            purge_all_key = "confirm_purge_trash"
            restore_all_key = "confirm_restore_all_trash"
            retention_text = (
                "不自动清理"
                if retention_days <= 0
                else f"自动保留 {retention_days} 天"
            )
            st.caption(f"回收站中的项目可以恢复，也可以彻底删除。当前策略：{retention_text}。")
            if st.button("♻️ 全部恢复", key="trash_restore_all_trigger"):
                activate_confirmation(restore_all_key)
                st.rerun()
            if render_confirmation_bar(
                restore_all_key,
                f"将把回收站中的 {len(trashed_records)} 条记录全部恢复到历史项目。",
                confirm_label="确认全部恢复",
            ):
                restored_count = len(restore_all_trashed_history_records())
                st.success(f"已恢复 {restored_count} 条记录。")
                st.rerun()
            render_batch_record_actions(trashed_records, mode="trash")
            if retention_days > 0 and st.button("⏱️ 立即清理过期回收站", key="trash_cleanup_expired"):
                purged_records = cleanup_expired_trashed_records()
                if purged_records:
                    st.success(f"已自动清理 {len(purged_records)} 条过期回收站记录。")
                else:
                    st.info("当前没有过期的回收站记录。")
                st.rerun()
            if st.button("🧨 清空回收站", key="trash_purge_all_trigger"):
                activate_confirmation(purge_all_key)
                st.rerun()
            if render_confirmation_bar(
                purge_all_key,
                f"将彻底删除回收站中的 {len(trashed_records)} 条记录及其本地文件，执行后不可恢复。",
                confirm_label="确认清空回收站",
            ):
                purged_count = len(purge_all_trashed_history_records())
                st.success(f"已彻底删除 {purged_count} 条回收站记录")
                st.rerun()
        else:
            st.info("回收站为空。删除的项目会先出现在这里。")
        for record in trashed_records:
            render_history_record_block(record, in_trash=True)

    with tab_files:
        render_file_management_tab(active_records + trashed_records)


# ==================== 智能组图页面 ====================
def show_combo_page():
    st.markdown(
        '<div class="page-title">🚀 智能组图工作流</div>', unsafe_allow_html=True
    )

    s = get_settings()
    templates = get_template_group("combo_types")
    provider = get_active_provider()
    if not provider or not provider.get("api_key"):
        st.error("⚠️ 未配置可用的提供商，请先在「提供商设置」中添加")
        return

    api_key = provider.get("api_key")
    base_url = provider.get("base_url", "")
    title_model = provider.get("title_model", "")
    vision_model = provider.get("vision_model", "")
    provider_image_model = provider.get("image_model", "")

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
        model_key = provider_image_model or s.get("default_model", "nano-banana")
        st.caption(
            f"当前按提供商配置使用：{MODELS.get(model_key, {'name': model_key}).get('name', model_key)}"
        )

        if st.session_state.session_tokens > 0:
            st.markdown(
                f'<div class="token-badge">🎯 {st.session_state.session_tokens:,} tokens</div>',
                unsafe_allow_html=True,
            )

    # 检查是否有已完成的结果需要显示
    if st.session_state.combo_generation_done and st.session_state.combo_results:
        st.markdown("## 📸 生成结果")
        display_generation_results(
            st.session_state.combo_results,
            st.session_state.combo_errors,
            st.session_state.combo_titles,
            st.session_state.get("combo_tokens_used", 0),
            "combo",
            st.session_state.get(
                "combo_result_title_language", DEFAULT_TARGET_LANGUAGE
            ),
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

    # Tab 1: 上传
    with tabs[0]:
        st.markdown(
            '<div class="help-section"><h4>💡 上传建议</h4><ul><li>至少上传1张<b>纯白底主体图</b>效果最佳</li><li>尺寸图建议上传原标注图作为参考</li></ul></div>',
            unsafe_allow_html=True,
        )

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

        btn_disabled = not st.session_state.combo_images
        if st.button(
            "🔍 AI分析商品",
            type="primary",
            use_container_width=True,
            disabled=btn_disabled,
        ):
            with st.spinner("🤖 AI正在分析..."):
                try:
                    client = GeminiClient(
                        api_key,
                        model_key,
                        base_url=base_url,
                        title_model=title_model,
                        vision_model=vision_model,
                    )
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
                    st.error(f"分析失败: {sanitize_task_error(str(e))}")

    # Tab 2: 选择类型
    with tabs[1]:
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

            enable_title, title_info, title_template, title_language = (
                render_title_gen_option("combo")
            )

            image_language = render_target_language_selector(
                "combo",
                "image_language",
                "🌐 图需 / 入图文案语言",
                "控制图需、入图文案和图片提示词里的目标语言。",
            )
            st.caption(
                f"当前图片文案语言: {get_title_language_caption(image_language)}"
            )

            st.markdown("---")
            aspect, size, thinking_level = render_gemini3_settings("combo", model_key)

            can_generate = total_count > 0 and total_count <= MAX_TOTAL_IMAGES

            if st.button(
                "📝 AI生成图需文案",
                type="primary",
                use_container_width=True,
                disabled=not can_generate,
            ):
                with st.spinner("🤖 生成中..."):
                    try:
                        client = GeminiClient(
                            api_key,
                            model_key,
                            base_url=base_url,
                            title_model=title_model,
                            vision_model=vision_model,
                        )
                        reqs = client.generate_requirements(
                            st.session_state.combo_anchor,
                            selected_types,
                            st.session_state.get("combo_tags_list", []),
                            image_language,
                        )
                        reqs = client.generate_en_copy(
                            st.session_state.combo_anchor,
                            reqs,
                            image_language,
                        )
                        st.session_state.combo_reqs = reqs
                        st.session_state.session_tokens += client.get_tokens_used()
                        st.success("✅ 生成完成！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"生成失败: {sanitize_task_error(str(e))}")

    # Tab 3: 图需文案
    with tabs[2]:
        reqs = st.session_state.combo_reqs
        if not reqs:
            st.info("👆 请先在「选择类型」生成图需文案")
        else:
            image_language = st.session_state.get(
                "combo_image_language", DEFAULT_TARGET_LANGUAGE
            )
            language_info = get_target_language(image_language)
            st.markdown(
                f'<div class="help-section"><h4>✏️ 编辑提示</h4><ul><li>{language_info["label"]}文案将直接出现在生成的图片上</li><li>避免使用认证词汇和绝对化用语</li></ul></div>',
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
                        st.markdown(f"**{language_info['label']}图需**")
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
                        st.markdown(f"**{language_info['label']}入图文案**")
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
        reqs = st.session_state.combo_reqs
        if not reqs:
            st.info("👆 请完成前面的步骤")
        elif not st.session_state.combo_generating:
            task_desc = f"**待生成: {len(reqs)} 张图片**"
            if st.session_state.get("combo_enable_title") and st.session_state.get(
                "combo_title_info"
            ):
                target_label = get_target_language(
                    st.session_state.get(
                        "combo_title_language", DEFAULT_TARGET_LANGUAGE
                    )
                )["label"]
                task_desc += (
                    " + **纯英文标题**"
                    if st.session_state.get(
                        "combo_title_language", DEFAULT_TARGET_LANGUAGE
                    )
                    == "en"
                    else f" + **英文 + {target_label} 标题**"
                )
            st.markdown(task_desc)
            if st.button("🚀 确认开始生成", type="primary", use_container_width=True):
                template_key = st.session_state.get("combo_title_template", "default")
                template_prompt = get_title_template_prompt(template_key)
                combo_images = st.session_state.get("combo_images", [])
                image_paths = []
                upload_dir = DATA_DIR / "task_uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                for idx, img in enumerate(combo_images):
                    filename = f"combo_{int(time.time())}_{idx + 1}.png"
                    path = upload_dir / filename
                    try:
                        img.save(path, format="PNG")
                        image_paths.append(str(path))
                    except Exception:
                        continue
                task, err = create_task(
                    "combo",
                    {
                        "provider_id": provider.get("id", ""),
                        "anchor": st.session_state.combo_anchor,
                        "reqs": reqs,
                        "image_paths": image_paths,
                        "total": len(reqs),
                        "image_language": st.session_state.get(
                            "combo_image_language", DEFAULT_TARGET_LANGUAGE
                        ),
                        "model": model_key,
                        "aspect": st.session_state.get("combo_aspect", "1:1"),
                        "size": st.session_state.get("combo_size", "1K"),
                        "thinking_level": st.session_state.get(
                            "combo_thinking_level", "high"
                        ),
                        "enable_title": st.session_state.get(
                            "combo_enable_title", False
                        ),
                        "title_info": st.session_state.get("combo_title_info", ""),
                        "template_prompt": template_prompt,
                        "title_language": st.session_state.get(
                            "combo_title_language", DEFAULT_TARGET_LANGUAGE
                        ),
                        "summary": f"智能组图任务 · {len(reqs)}张",
                    },
                )
                if task:
                    schedule_task_workers()
                    st.success(f"✅ 已加入任务中心：{task['id']}")
                else:
                    st.error(err)

    show_footer()


# ==================== 快速出图页面 ====================
def show_smart_page():
    st.markdown('<div class="page-title">🎨 快速出图 / 图片翻译</div>', unsafe_allow_html=True)

    s = get_settings()
    templates = get_template_group("smart_types")
    provider = get_active_provider()
    if not provider or not provider.get("api_key"):
        st.error("⚠️ 未配置可用的提供商，请先在「提供商设置」中添加")
        return

    api_key = provider.get("api_key")
    base_url = provider.get("base_url", "")
    title_model = provider.get("title_model", "")
    vision_model = provider.get("vision_model", "")
    provider_image_model = provider.get("image_model", "")

    # 检查是否有已完成的结果
    if st.session_state.smart_generation_done and st.session_state.smart_results:
        st.markdown("## 📸 生成结果")
        display_generation_results(
            st.session_state.smart_results,
            st.session_state.smart_errors,
            st.session_state.smart_titles,
            st.session_state.get("smart_tokens_used", 0),
            "smart",
            st.session_state.get(
                "smart_result_title_language", DEFAULT_TARGET_LANGUAGE
            ),
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
        st.markdown(
            "这里包含两种工作方式：创意出图，以及图片翻译（合规优先的保版翻译）。如果你要做原图文案替换，请选择“图片翻译”模式。"
        )

    workflow_mode = st.radio(
        "工作模式",
        ["creative", "translate"],
        horizontal=True,
        format_func=lambda x: {
            "creative": "✨ 创意出图",
            "translate": "🈯 图片翻译（合规翻译）",
        }.get(x, x),
        key="smart_workflow_mode",
    )

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

    if workflow_mode == "creative":
        selected_types, total_count = render_type_selector(
            templates, prefix="smart", max_per_type=5, max_total=20
        )
        enable_title, title_info, title_template, title_language = (
            render_title_gen_option("smart")
        )
        translation_template = "preserve_layout"
    else:
        selected_types, total_count = {}, len(images)
        enable_title, title_info, title_template, title_language = (
            False,
            "",
            "default",
            DEFAULT_TARGET_LANGUAGE,
        )
        (
            enabled_translation_templates,
            translation_options,
            translation_template_names,
        ) = build_translation_template_selector_options()
        translation_template = st.selectbox(
            "翻译保版模板",
            translation_options,
            format_func=lambda key: translation_template_names.get(key, key),
            key="smart_translation_template",
            help="选择当前翻译任务使用的保版翻译策略模板。",
        )
        st.info(
            f"当前为合规翻译模式：将按 {get_compliance().get('presets', {}).get(st.session_state.get('user_compliance_mode', 'strict'), {}).get('name', '当前合规模式')} 执行保版翻译。"
        )
        selected_translation_info = enabled_translation_templates.get(translation_template, {})
        if selected_translation_info:
            st.caption(
                f"当前模板说明: {selected_translation_info.get('desc', '')}"
            )

    image_language = render_target_language_selector(
        "smart",
        "image_language",
        "🌐 图片文案语言",
        "控制图片内文案和相关提示词使用的目标语言。",
    )
    st.caption(f"当前图片文案语言: {get_title_language_caption(image_language)}")

    st.markdown("---")

    model = provider_image_model or s.get("default_model", "nano-banana")
    st.caption(
        f"当前按提供商配置使用出图模型：{MODELS.get(model, {'name': model}).get('name', model)}"
    )
    aspect, size, thinking_level = render_gemini3_settings("smart", model)

    can_gen = bool(images) and (
        workflow_mode == "translate" or (name and total_count > 0)
    )

    if st.button(
        "🚀 开始翻译" if workflow_mode == "translate" else "🚀 开始生成",
        type="primary",
        use_container_width=True,
        disabled=not can_gen,
    ):
        image_paths = _save_uploaded_images(files or [], f"smart_{int(time.time())}")
        template_prompt = get_title_template_prompt(title_template)
        task, err = create_task(
            "translate" if workflow_mode == "translate" else "smart",
            {
                "provider_id": provider.get("id", ""),
                "image_paths": image_paths,
                "name": name,
                "material": material or "",
                "selected_types": selected_types,
                "total": total_count,
                "image_language": image_language,
                "model": model,
                "aspect": aspect,
                "size": size,
                "thinking_level": thinking_level,
                "enable_title": enable_title,
                "title_info": title_info,
                "title_template": title_template,
                "template_prompt": template_prompt,
                "title_language": title_language,
                "translation_template": translation_template,
                "compliance_mode": st.session_state.get(
                    "user_compliance_mode", "strict"
                ),
                "summary": (
                    f"组图翻译任务 · {name or '未命名项目'} · {len(images)}张"
                    if workflow_mode == "translate"
                    else f"快速出图任务 · {name} · {total_count}张"
                ),
            },
        )
        if task:
            schedule_task_workers()
            st.success(f"✅ 已加入任务中心：{task['id']}")
        else:
            st.error(err)

    show_footer()


# ==================== 标题生成页面 ====================
def show_title_page():
    st.markdown(
        '<div class="page-title">🏷️ 智能标题生成</div>',
        unsafe_allow_html=True,
    )

    provider = get_active_provider()
    if not provider or not provider.get("api_key"):
        st.error("⚠️ 未配置可用的提供商，请先在「提供商设置」中添加")
        return

    api_key = provider.get("api_key")
    base_url = provider.get("base_url", "")
    title_model = provider.get("title_model", "")
    vision_model = provider.get("vision_model", "")

    title_templates = get_title_templates()

    st.markdown(
        f"""<div class="help-section">
        <h4>🎯 输出规则</h4>
        <ul>
            <li><b>默认英文优先</b> - 可输出纯英文，或英文 + 所选目标语言</li>
            <li><b>英文字符</b> - {MIN_TITLE_EN_CHARS}-{MAX_TITLE_EN_CHARS}字符</li>
            <li><b>三种策略</b> - 搜索优化/转化优化/差异化</li>
        </ul>
    </div>""",
        unsafe_allow_html=True,
    )

    title_language = render_target_language_selector(
        "standalone_title",
        "target_language",
        "🌐 标题目标语言",
        "标题默认优先英文；若选择英语，则输出纯英文标题。",
    )
    st.caption(f"当前标题模型：{title_model or '未配置'}")
    st.caption(f"当前视觉模型：{vision_model or '未配置'}")
    if title_language == "en":
        st.caption("当前输出: 🇺🇸 纯英文标题")
    else:
        st.caption(
            f"当前输出: 🇺🇸 English + {get_title_language_caption(title_language)}"
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

    enabled_templates, template_options, template_names = (
        build_title_template_selector_options(
            input_mode=input_mode, include_custom=(input_mode != "🖼️ 图片分析")
        )
    )

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
            "提示词 ({product_info} 为占位符，可选 {target_language_name})",
            height=200,
            key="custom_title_prompt",
            placeholder="Generate titles in English or English plus {target_language_name} for: {product_info}",
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
        "🚀 生成标题",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
    ):
        image_paths = _save_uploaded_images(
            uploaded_images, f"title_{int(time.time())}"
        )
        task, err = create_task(
            "title",
            {
                "provider_id": provider.get("id", ""),
                "product_info": product_info,
                "template_prompt": final_prompt,
                "title_language": title_language,
                "image_paths": image_paths,
                "summary": f"标题任务 · {get_target_language(title_language)['label']}",
            },
        )
        if task:
            schedule_task_workers()
            st.success(f"✅ 已加入任务中心：{task['id']}")
        else:
            st.error(err)

    show_footer()


# ==================== 主应用 ====================
def main_app():
    schedule_task_workers()
    st.session_state["_footer_rendered"] = False
    current_page = get_nav_page()
    with st.sidebar:
        st.markdown(f"### 🍌 {APP_NAME}")
        st.markdown("---")
        provider = get_active_provider()
        if provider:
            st.caption(f"当前提供商: {provider.get('name', '')}")
        current_page = render_sidebar_nav_section("功能区", MAIN_NAV_ITEMS, current_page)
        st.markdown("---")
        current_page = render_sidebar_nav_section("管理与配置", MANAGEMENT_NAV_ITEMS, current_page)
        st.markdown("---")
        render_task_center()

        if st.button("🚪 退出", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    set_nav_page(current_page)
    render_global_toolbar(current_page)

    if current_page == "🚀 智能组图":
        show_combo_page()
    elif current_page == "🎨 快速出图 / 图片翻译":
        show_smart_page()
    elif current_page == "🏷️ 标题生成":
        show_title_page()
    elif current_page == PROJECT_CENTER_PAGE:
        show_project_center()
    elif current_page == "🧩 模板库":
        show_template_library()
    elif current_page == "⚙️ 提供商设置":
        show_provider_settings()
    else:
        show_settings_center()

    show_footer()


# ==================== 主入口 ====================
def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🍌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_style()
    apply_proxy_settings()
    init_session()

    main_app()


if __name__ == "__main__":
    main()
