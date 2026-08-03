"""电商出图工作台.

个人 self-hosted 主线，支持 desktop 与 server 两种运行模式。
"""

import streamlit as st
from PIL import Image, ImageDraw
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import hashlib
import hmac
import html as _html_mod
import base64
import copy
import functools
import zipfile
import random
import time
import subprocess
import tempfile
import shutil
import urllib.request
import urllib.error
import urllib.parse
import logging
import logging.handlers
import uuid
from collections.abc import Mapping
from datetime import datetime, date, timedelta
from pathlib import Path
from google import genai
from google.genai import types
from task_engine import TaskEngine, TaskExecution, TaskHandler
from task_status import TASK_COMPLETED_STATUSES, TASK_TERMINAL_STATUSES
from task_store import SqliteTaskStore, TaskCapacityError
from suite_output import normalize_suite_image

# ==================== 配置常量 ====================
APP_VERSION = "V15.2.1"
APP_AUTHOR = "企鹅 & 小明"
APP_COMMERCIAL = "企鹅 & Jerry"
APP_NAME = "电商出图工作台"  # 内部常量：用于本地目录等功能性路径，勿改
BRAND_NAME = "TuLite"
BRAND_TITLE = "TuLite · 跨境出图工作台"
BRAND_CAPTION = "图 Lite · 跨境出图"
# 品牌 Logo（内联 SVG，无外部资源）：墨蓝描边圆角方框 + 画框山形 + 橙色太阳点 + 字标
TULITE_LOGO_HTML = """
<div style="display:flex;align-items:center;gap:10px;height:56px;margin:2px 0 6px 0;">
  <svg width="44" height="44" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <rect x="3" y="3" width="38" height="38" rx="8" fill="#ffffff" stroke="#1B2A4A" stroke-width="2.5"/>
    <circle cx="29" cy="14.5" r="3.5" fill="#FF7A45"/>
    <path d="M9 31 L18 19 L24 26 L28 22 L35 31 Z" fill="#1B2A4A"/>
  </svg>
  <div style="line-height:1.15;">
    <div style="font-size:20px;font-weight:800;color:#1B2A4A;letter-spacing:0.2px;">TuLite</div>
    <div style="font-size:11px;color:#64748B;">图 Lite · 跨境出图</div>
  </div>
</div>
"""
DEMO_PROVIDER_ID = "local-demo-admin"
DEMO_PROVIDER_KEY = "DEMO-ADMIN-KEY"
DEMO_PROVIDER_NAME = "本地演示管理员"


def esc(v):
    """HTML 转义用户/AI 可控内容，防止注入 unsafe_allow_html 渲染。"""
    return _html_mod.escape(str(v or ""), quote=True)


def demo_mode_enabled() -> bool:
    return os.getenv("XIAOBAITU_DEMO_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "demo",
    }


def is_demo_api_key(api_key: str) -> bool:
    return (api_key or "").strip() == DEMO_PROVIDER_KEY


def is_demo_provider(provider: dict) -> bool:
    return bool(provider and is_demo_api_key(resolve_provider_api_key(provider)))


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

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger("xiaobaitu")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _log_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    _file_handler = logging.handlers.RotatingFileHandler(
        str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _file_handler.setFormatter(_log_formatter)
    logger.addHandler(_file_handler)
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(_log_formatter)
    logger.addHandler(_stream_handler)
    logger.propagate = False

SETTINGS_FILE = DATA_DIR / "settings.json"
PROVIDERS_FILE = DATA_DIR / "providers.json"
PROMPTS_FILE = DATA_DIR / "prompts.json"
COMPLIANCE_FILE = DATA_DIR / "compliance.json"
TEMPLATES_FILE = DATA_DIR / "templates.json"
TITLE_TEMPLATES_FILE = DATA_DIR / "title_templates.json"
TASKS_FILE = DATA_DIR / "tasks.json"
TASK_DB_FILE = DATA_DIR / "tasks.sqlite3"
HISTORY_FILE = DATA_DIR / "history.json"
HISTORY_DIR = DATA_DIR / "history"
INSTANCE_FILE = DATA_DIR / "instance.json"

KEYCHAIN_SERVICE = "ecommerce-image-workbench"
MAX_TASK_QUEUE = 5
MAX_HISTORY_RECORDS = 300
MAX_ACTIVE_TASKS = 2
HISTORY_RECORD_ACTIVE = "active"
HISTORY_RECORD_TRASHED = "trashed"
GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS", "60")
)
GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv("GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS", "300")
)
IMAGE_RETRY_COOLDOWN_SECONDS = int(
    os.getenv("IMAGE_RETRY_COOLDOWN_SECONDS", "90")
)
RETRYABLE_IMAGE_ERROR_TYPES = frozenset(
    {"upstream_timeout", "provider_connection", "rate_limited"}
)
FAILED_ITEM_RETRY_SUMMARY_PREFIX = "重试失败项 · "
TASK_RUNNER_LEASE_SECONDS = max(
    15, int(os.getenv("TASK_RUNNER_LEASE_SECONDS", "30"))
)
TASK_RUNNER_HEARTBEAT_SECONDS = max(
    3, min(10, TASK_RUNNER_LEASE_SECONDS // 3)
)
TASK_SUPERVISOR_INTERVAL_SECONDS = max(
    2, int(os.getenv("TASK_SUPERVISOR_INTERVAL_SECONDS", "5"))
)

# OpenAI 兼容协议（GPT Image 2 等）的默认配置
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_TEXT_MODEL = os.getenv("OPENAI_DEFAULT_TEXT_MODEL", "gpt-4o-mini")
OPENAI_DEFAULT_IMAGE_MODEL = os.getenv("OPENAI_DEFAULT_IMAGE_MODEL", "gpt-image-2")

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
    {
        "code": "de",
        "label": "德语",
        "english_name": "German",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "copy_tag": "DE",
    },
    {
        "code": "it",
        "label": "意大利语",
        "english_name": "Italian",
        "native_name": "Italiano",
        "flag": "🇮🇹",
        "copy_tag": "IT",
    },
    {
        "code": "pt",
        "label": "葡萄牙语",
        "english_name": "Portuguese",
        "native_name": "Português",
        "flag": "🇵🇹",
        "copy_tag": "PT",
    },
    {
        "code": "ko",
        "label": "韩语",
        "english_name": "Korean",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "copy_tag": "KO",
    },
    {
        "code": "id",
        "label": "印尼语",
        "english_name": "Indonesian",
        "native_name": "Bahasa Indonesia",
        "flag": "🇮🇩",
        "copy_tag": "ID",
    },
    {
        "code": "ms",
        "label": "马来语",
        "english_name": "Malay",
        "native_name": "Bahasa Melayu",
        "flag": "🇲🇾",
        "copy_tag": "MS",
    },
    {
        "code": "ar",
        "label": "阿拉伯语",
        "english_name": "Arabic",
        "native_name": "العربية",
        "flag": "🇸🇦",
        "copy_tag": "AR",
    },
    {
        "code": "tr",
        "label": "土耳其语",
        "english_name": "Turkish",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "copy_tag": "TR",
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
    "German",
    "德语",
    "Italian",
    "意大利语",
    "Portuguese",
    "葡萄牙语",
    "Korean",
    "韩语",
    "Indonesian",
    "印尼语",
    "Malay",
    "马来语",
    "Arabic",
    "阿拉伯语",
    "Turkish",
    "土耳其语",
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
    "gpt-image-2": {
        "name": "🎯 GPT Image 2",
        "resolutions": ["1K", "2K"],
        "max_refs": 10,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
        "api_format": "openai",
    },
    "gpt-image-2-x": {
        "name": "🎯 GPT Image 2 X",
        "resolutions": ["1K", "2K"],
        "max_refs": 10,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
        "api_format": "openai",
    },
    "gpt-image-2-auto": {
        "name": "🎯 GPT Image 2 Auto",
        "resolutions": ["1K", "2K"],
        "max_refs": 10,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
        "api_format": "openai",
    },
    "gpt-image-1.5": {
        "name": "🖼️ GPT Image 1.5",
        "resolutions": ["1K", "2K"],
        "max_refs": 10,
        "thinking_levels": [],
        "default_thinking": None,
        "supports_thinking": False,
        "api_format": "openai",
    },
}

# ==================== 标题/视觉理解模型目录 ====================
# 说明：family 字段仅用于下拉框展示分组图标，不参与协议判断。
# 实际请求协议永远由 provider 的 provider_type（gemini/openai）决定；
# 选择了协议不匹配的模型名会在调用时报错（已经过 sanitize_task_error 处理为中文提示）。
TITLE_VISION_MODELS = {
    "gpt-4o": {"name": "🔵 GPT-4o", "family": "openai"},
    "gpt-4o-mini": {"name": "🔵 GPT-4o Mini", "family": "openai"},
    "gpt-5.4": {"name": "🔵 GPT-5.4", "family": "openai"},
    "gpt-5.4-mini": {"name": "🔵 GPT-5.4 Mini", "family": "openai"},
    "gemini-2.5-flash": {"name": "🟢 Gemini 2.5 Flash", "family": "gemini"},
    "gemini-3.1-flash-lite-preview": {
        "name": "🟢 Gemini 3.1 Flash Lite Preview",
        "family": "gemini",
    },
    "gemini-3-pro-preview": {"name": "🟢 Gemini 3 Pro Preview", "family": "gemini"},
    "grok-2-vision-1212": {"name": "⚫ Grok-2 Vision 1212", "family": "grok"},
    "grok-4": {"name": "⚫ Grok-4", "family": "grok"},
}

TITLE_VISION_MODEL_ORDER = list(TITLE_VISION_MODELS.keys())


def format_title_vision_model(model_id: str) -> str:
    """下拉框 format_func：按 family 图标展示模型名。"""
    info = TITLE_VISION_MODELS.get(model_id)
    if info:
        return info["name"]
    return model_id


def resolve_default_title_vision_model(current_value: str) -> str:
    """根据当前 provider 配置的值，在目录里找一个合理的默认选中项。

    命中目录直接用；找不到时尝试按 provider_type 猜测的 family 退回该家族第一个；
    实在找不到就用目录第一项，不抛异常。
    """
    value = (current_value or "").strip()
    if value in TITLE_VISION_MODELS:
        return value
    # 尝试根据关键字猜测家族，退回该家族第一个模型
    lowered = value.lower()
    family_guess = None
    if "gpt" in lowered or "openai" in lowered:
        family_guess = "openai"
    elif "gemini" in lowered:
        family_guess = "gemini"
    elif "grok" in lowered:
        family_guess = "grok"
    if family_guess:
        for mid, info in TITLE_VISION_MODELS.items():
            if info["family"] == family_guess:
                return mid
    return TITLE_VISION_MODEL_ORDER[0]


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

MAIN_NAV_ITEMS = ["🚀 智能组图", "✨ 文字生图", "🎨 快速出图 / 图片翻译", "🏷️ 标题生成"]
PROJECT_CENTER_PAGE = "📚 项目中心"
TASK_CENTER_PAGE = "📡 任务中心"
MANAGEMENT_NAV_ITEMS = [TASK_CENTER_PAGE, "🧩 模板库", PROJECT_CENTER_PAGE, "⚙️ 提供商设置", "🛠️ 系统设置"]

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
    "max_active_tasks": MAX_ACTIVE_TASKS,
    "max_task_queue": MAX_TASK_QUEUE,
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
    "image_prompt": """Professional commercial product photography for an ecommerce listing.
Product: {product_name}
Category: {category}
Image type: {image_type}
Style: {style_hint}
Scene: {scene}
Text overlay ({output_language_name} ONLY):
{text_content}
Photography: studio softbox lighting, soft natural shadow under the product, clean seamless background, sharp focus, high detail, true-to-life colors.
Composition: product is the hero, centered, filling about 70-80% of the frame, clear visual hierarchy, uncluttered layout.
CRITICAL: Product must exactly match the reference image in shape, color, material and logo. If the image contains text, use {output_language_name} only. Keep the image free of watermarks and of any text beyond the overlay above. Professional ecommerce style.
Aspect ratio: {aspect_ratio}""",
    "size_image_prompt": """Professional product dimension diagram for an ecommerce listing.
Product: {product_name}
Style: Clean technical illustration on a pure white background, product rendered accurately and centered, filling about 70% of the frame, flat even lighting, no decorative props.
REQUIRED: Clear bidirectional arrow lines aligned to each measured edge. Dual unit measurements: XX.XX inch / XX.X cm. Use word "inch" NOT "in". Clean sans-serif font, high-contrast dark labels, generous spacing so every number stays legible. Use {output_language_name} for descriptive labels and notes while keeping inch and cm for units. Keep the diagram free of watermarks and unrelated text.
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
    "image_language_instruction": "If the image contains any text, ALL text MUST be in {output_language_name} ({output_language_native}) only. Do not mix multiple languages.",
    "title_language_rules_en": """TARGET LANGUAGE RULES
- Output English only.
- Generate exactly 3 English titles with no translation lines.
- Every English title must be {min_title_en_chars}-{max_title_en_chars} characters.
- Output exactly 3 lines total with no labels or commentary.""",
    "title_language_rules_bilingual": """TARGET LANGUAGE RULES
- Keep English as the fixed source language for every first line.
- The second line of each title must be in {target_language_name} ({target_language_native}).
- {translation_language_rule}
- Output exactly 6 lines total with no labels or commentary.
- Line order must be English line then {target_language_name} line, repeated 3 times.""",
    "temu_tri_title_prompt": """你是资深跨境电商标题专家。根据提供的商品文字信息与商品图片（如有），为 TEMU 平台同一款商品产出三条标题：中文、西班牙语（Español）、法语（Français）。

商品信息：
{product_info}

{template_context}

【幕后工作流程（对用户不可见，最终只交付成品）】
1. 分别以中文、西班牙语、法语母语文案师的身份，各写一条标题；
2. 切换为资深 TEMU 运营与合规专家身份，按下方三层合规框架逐条自查，发现问题立即改写；
3. 只输出最终定稿结果，禁止输出思考过程、自查记录或任何解释。

【三层合规框架】
第一层 · 绝对禁用（任何情况下不得出现）：
- 绝对化用语：最/第一/唯一/100%/保证/顶级/完美；Mejor/No.1/Único/Perfecto/100%/Garantía/Superior；Meilleur/No.1/Unique/Parfait/100%/Garantie/Supérieur
- 虚假认证：FDA/CE/认证/Certificado/Certifié 等认证类词汇
- 材质替换：gold→金色/Dorado/Doré；silver→银色/Plateado/Argenté；diamond→水晶·仿钻/Cristal·Estrás/Cristal·Strass

第二层 · 条件禁用（仅当商品确实具备该属性、且商品信息明确支持时才可使用，否则一律省略）：
- 防水 waterproof/Impermeable/Imperméable
- 保温/隔热 insulated/Aislante/Isolant
- 抗菌 antibacterial/Antibacteriano/Antibactérien
- 环保·有机 eco·organic/Ecológico·Orgánico/Écologique·Bio
- 儿童相关词汇（仅当商品确实属于儿童品类时可用）

第三层 · 语义风险自查（看含义而非词表）：
- 不得出现商品信息无法支撑的功效、安全、环保、医疗暗示
- 不得用同义改写规避第一层禁用词
- 不得暗示官方认证或针对未成年人营销
- 命中任意一条立即改写该标题

【质量原则】
- 核心产品词放最前面；不堆砌同义词
- 母语级自然表达，不是逐字翻译；三种语言各自贴合本地买家真实搜索习惯选长尾词
- 宁可精准不要凑数
- 结构公式（灵活运用）：[核心产品词]+[关键属性/材质]+[尺寸/规格]+[使用场景]+[风格/颜色]
- 三条标题按各自语言的本地搜索表达组织，禁止三种语言互相逐字对译

【硬性要求】
- 字符区间为硬性要求（含空格）：中文 40-80 字符；西班牙语和法语 150-200 字符。写完后逐条数字符：中文不足 40 或超过 80 时增删属性词至达标；西语/法语不足 150 时必须继续补充真实合规的长尾属性词（材质、规格、场景、人群、风格、颜色等）直到达标，超过 200 时删减。这些区间对各自语言都完全可以达到，不要轻易放弃
- 西班牙语和法语标题必须附中文回译（back_translation_zh）
- 例外规则（极少使用）：仅当某语言因合规原因（而非长度原因）实在无法产出干净标题时，该语言才不输出标题，改为在 issues 中用一句话说明原因。长度不足不是使用例外规则的理由

【输出格式：只输出下面结构的 JSON，不要 markdown 代码块，不要任何多余文字】
{"titles": [{"lang": "zh", "title": "..."}, {"lang": "es", "title": "...", "back_translation_zh": "..."}, {"lang": "fr", "title": "...", "back_translation_zh": "..."}], "issues": []}""",
}

DEFAULT_TEMPLATES = {
    "combo_types": {
        "main": {
            "name": "主图白底",
            "icon": "🎯",
            "desc": "纯白背景产品主图",
            "hint": "Pure seamless white background, product centered filling 70-80% of frame, soft grounding shadow, no props, no text",
            "enabled": True,
            "order": 1,
        },
        "feature": {
            "name": "功能卖点图",
            "icon": "⭐",
            "desc": "突出商品核心卖点与优势的说明图",
            "hint": "Feature highlights with clean callout lines and short labels, product hero centered, tidy uncluttered layout",
            "enabled": True,
            "order": 2,
        },
        "scene": {
            "name": "场景应用图",
            "icon": "🏠",
            "desc": "展示商品在真实使用场景中的效果",
            "hint": "Realistic lifestyle scene, product in natural use, warm inviting light, believable environment, product clearly visible",
            "enabled": True,
            "order": 3,
        },
        "detail": {
            "name": "细节特写图",
            "icon": "🔍",
            "desc": "放大展示材质、工艺和细节做工",
            "hint": "Macro close-up shot, texture and craftsmanship details, shallow depth of field, razor-sharp focus on material",
            "enabled": True,
            "order": 4,
        },
        "size": {
            "name": "尺寸规格图",
            "icon": "📐",
            "desc": "展示尺寸、规格或参数信息的说明图",
            "hint": "Clean technical dimension diagram, bidirectional arrows, dual inch/cm units, pure white background",
            "enabled": True,
            "order": 5,
            "special": True,
        },
        "compare": {
            "name": "对比优势图",
            "icon": "⚖️",
            "desc": "用对比方式突出商品优势与差异点",
            "hint": "Clear side-by-side comparison layout, consistent lighting on both sides, our product's advantage clearly highlighted",
            "enabled": True,
            "order": 6,
        },
        "package": {
            "name": "包装清单图",
            "icon": "📦",
            "desc": "展示包装内包含的商品与配件内容",
            "hint": "Neat flat lay of all package contents on a clean background, evenly lit, every item fully visible and labeled",
            "enabled": True,
            "order": 7,
        },
        "steps": {
            "name": "操作引导图",
            "icon": "📋",
            "desc": "用于说明安装、使用流程或操作顺序的信息图",
            "hint": "Numbered step-by-step visual guide, clean infographic layout, consistent product rendering across steps",
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
FILE_IO_LOCK = threading.RLock()


def load_json(fp, default=None):
    with FILE_IO_LOCK:
        try:
            if fp.exists():
                with open(fp, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return default.copy() if default else {}


def save_json(fp, data):
    with FILE_IO_LOCK:
        try:
            tmp = str(fp) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(fp))
            return True
        except:
            return False


class _InterProcessHistoryLock:
    """Reentrant thread lock plus OS lock for the JSON history index."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._handle = None

    def __enter__(self):
        self._thread_lock.acquire()
        try:
            if self._depth == 0:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._handle = open(self.path, "a+b")
                if os.name == "nt":
                    import msvcrt

                    self._handle.seek(0, os.SEEK_END)
                    if self._handle.tell() == 0:
                        self._handle.write(b"\0")
                        self._handle.flush()
                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
            self._depth += 1
            return self
        except Exception:
            if self._handle:
                self._handle.close()
                self._handle = None
            self._thread_lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self._depth -= 1
            if self._depth == 0 and self._handle:
                if os.name == "nt":
                    import msvcrt

                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                self._handle.close()
                self._handle = None
        finally:
            self._thread_lock.release()
        return False


@st.cache_resource(show_spinner=False)
def get_history_lock():
    return _InterProcessHistoryLock(Path(str(HISTORY_FILE) + ".lock"))


def synchronized_history_mutation(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with get_history_lock():
            return func(*args, **kwargs)

    return wrapper


_CONFIG_CACHE = {}


def _cached_config(fp, builder):
    """按文件 mtime 缓存合并后的配置。线程安全（FILE_IO_LOCK），
    不依赖 st.cache_data（后台工作线程也会调用这些函数）。"""
    fp_str = str(fp)
    try:
        mtime = os.path.getmtime(fp_str) if fp.exists() else -1.0
    except OSError:
        mtime = -1.0
    with FILE_IO_LOCK:
        cached = _CONFIG_CACHE.get(fp_str)
        if cached and cached[0] == mtime:
            return copy.deepcopy(cached[1])
    value = builder()
    with FILE_IO_LOCK:
        _CONFIG_CACHE[fp_str] = (mtime, copy.deepcopy(value))
    return value


def get_settings():
    def _build():
        s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        for k, v in DEFAULT_SETTINGS.items():
            if k not in s:
                s[k] = v
        return s

    return _cached_config(SETTINGS_FILE, _build)


def get_task_limits(settings=None):
    """Return validated runtime queue limits, with environment overrides.

    Keep the legacy constants as defaults so older settings files remain safe,
    while allowing operators to tune concurrency from System Settings.
    """
    s = settings or get_settings()
    try:
        max_active = int(
            os.getenv("MAX_ACTIVE_TASKS") or s.get("max_active_tasks") or MAX_ACTIVE_TASKS
        )
    except (TypeError, ValueError):
        max_active = MAX_ACTIVE_TASKS
    try:
        max_queue = int(
            os.getenv("MAX_TASK_QUEUE") or s.get("max_task_queue") or MAX_TASK_QUEUE
        )
    except (TypeError, ValueError):
        max_queue = MAX_TASK_QUEUE
    return max(1, min(max_active, 16)), max(1, min(max_queue, 100))


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


SECRET_KEY_FILE = DATA_DIR / ".secret_key"


def _get_or_create_local_secret_key() -> bytes:
    """Local symmetric encryption key used as a fallback for storing provider
    API keys when the macOS Keychain isn't available (e.g. Linux server/
    container deployments). Generated once and reused thereafter."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return b""
    env_key = (os.getenv("XIAOBAITU_SECRET_KEY") or "").strip()
    if env_key:
        key_bytes = env_key.encode("utf-8")
        try:
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            logger.warning(
                "XIAOBAITU_SECRET_KEY 不是有效的 Fernet 密钥，回退到本地密钥文件"
            )
    try:
        if SECRET_KEY_FILE.exists():
            key = SECRET_KEY_FILE.read_bytes().strip()
            if key:
                return key
        key = Fernet.generate_key()
        SECRET_KEY_FILE.write_bytes(key)
        try:
            os.chmod(str(SECRET_KEY_FILE), 0o600)
        except OSError:
            pass
        return key
    except Exception:
        logger.exception("failed to load/create local secret key for encrypted provider storage")
        return b""


def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    try:
        from cryptography.fernet import Fernet

        key = _get_or_create_local_secret_key()
        if not key:
            return ""
        return Fernet(key).encrypt(plain_text.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.exception("failed to encrypt provider secret")
        return ""


def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        from cryptography.fernet import Fernet

        key = _get_or_create_local_secret_key()
        if not key:
            return ""
        return Fernet(key).decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.exception("failed to decrypt provider secret")
        return ""


def encrypted_storage_available() -> bool:
    try:
        import cryptography  # noqa: F401

        return True
    except ImportError:
        return False


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


def normalize_provider_base_url(provider_type: str, base_url: str) -> str:
    normalized_type = (provider_type or "").strip().lower()
    normalized_base = (base_url or "").strip()
    if normalized_type != "openai" or not normalized_base:
        return normalized_base
    try:
        parsed = urllib.parse.urlsplit(normalized_base)
    except ValueError:
        return normalized_base
    if not parsed.scheme or not parsed.netloc or parsed.path not in ("", "/"):
        return normalized_base
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "/v1", parsed.query, parsed.fragment)
    )


def _normalize_provider_entry(entry):
    if not isinstance(entry, dict):
        return None
    pid = (entry.get("id") or "").strip() or _new_provider_id()
    name = (entry.get("name") or "").strip() or "个人提供商"
    provider_type = (entry.get("provider_type") or "gemini").strip().lower()
    api_key = (entry.get("api_key") or "").strip()
    base_url = normalize_provider_base_url(
        provider_type,
        entry.get("base_url") or "",
    )
    title_model = (entry.get("title_model") or "").strip()
    vision_model = (entry.get("vision_model") or "").strip()
    image_model = (entry.get("image_model") or "").strip()
    enabled = bool(entry.get("enabled", True))
    is_default = bool(entry.get("is_default", False))
    secret_storage = (entry.get("secret_storage") or "plain").strip().lower()
    keychain_account = (
        entry.get("keychain_account") or ""
    ).strip() or _keychain_account(pid)
    model_catalog = entry.get("model_catalog")
    if not isinstance(model_catalog, list):
        model_catalog = []
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
        "model_catalog": _normalize_model_catalog(model_catalog),
        "model_catalog_updated_at": str(entry.get("model_catalog_updated_at") or "").strip(),
        "model_catalog_error": str(entry.get("model_catalog_error") or "").strip(),
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
    ok = save_json(PROVIDERS_FILE, data)
    if ok:
        try:
            os.chmod(str(PROVIDERS_FILE), 0o600)
        except OSError:
            pass
    return ok


def resolve_provider_api_key(provider: dict) -> str:
    if not provider:
        return ""
    storage = provider.get("secret_storage")
    if storage == "keychain":
        return get_keychain_secret(provider.get("keychain_account"))
    if storage == "encrypted":
        return decrypt_secret(provider.get("api_key") or "")
    if storage == "environment":
        return (
            os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        ).strip()
    if storage == "runtime":
        return (provider.get("api_key") or "").strip()
    # "plain" (legacy) or unset: read raw value as-is for backward compat.
    return (provider.get("api_key") or "").strip()


def persist_provider_secret(provider: dict, api_key: str):
    api_key = (api_key or "").strip()
    if not provider:
        return provider, False
    if not api_key:
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
    if api_key and encrypted_storage_available():
        cipher_text = encrypt_secret(api_key)
        if cipher_text:
            provider["secret_storage"] = "encrypted"
            provider["api_key"] = cipher_text
            return provider, True
    raise RuntimeError(
        "当前环境无法安全保存 API Key，请配置 Keychain 或 XIAOBAITU_SECRET_KEY。"
    )


def provider_secret_storage_notice(provider: dict) -> str:
    storage = (provider or {}).get("secret_storage")
    if storage == "keychain":
        return "API Key 已安全保存到 Keychain。"
    if storage == "encrypted":
        return "API Key 已加密保存。"
    return ""


def migrate_provider_secrets(data):
    changed = False
    for provider in data.get("providers", []):
        raw_key = (provider.get("api_key") or "").strip()
        if (
            raw_key
            and provider.get("secret_storage") in (None, "", "plain")
            and (keychain_available() or encrypted_storage_available())
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
        "api_key": "",
        "base_url": "",
        "title_model": s.get("default_title_model", "gemini-3.1-flash-lite-preview"),
        "vision_model": s.get("default_vision_model", "gemini-3.1-flash-lite-preview"),
        "image_model": s.get("default_model", "gemini-3.1-flash-image-preview"),
        "enabled": True,
        "is_default": True,
        "secret_storage": "environment",
    }
    data["providers"] = [provider]
    data["current_id"] = provider["id"]
    return data


def build_demo_provider() -> dict:
    s = get_settings()
    return {
        "id": DEMO_PROVIDER_ID,
        "name": DEMO_PROVIDER_NAME,
        "provider_type": "gemini",
        "api_key": DEMO_PROVIDER_KEY,
        "base_url": "",
        "title_model": s.get("default_title_model", "gemini-3.1-flash-lite-preview"),
        "vision_model": s.get("default_vision_model", "gemini-3.1-flash-lite-preview"),
        "image_model": s.get("default_model", "gemini-3.1-flash-image-preview"),
        "enabled": True,
        "is_default": True,
        "secret_storage": "plain",
        "keychain_account": _keychain_account(DEMO_PROVIDER_ID),
    }


def ensure_demo_provider(data: dict, set_current: bool = False) -> dict:
    data = _normalize_providers_data(data)
    providers = data.get("providers", [])
    demo_provider = build_demo_provider()
    existing = next((p for p in providers if p.get("id") == DEMO_PROVIDER_ID), None)
    if existing:
        existing.update(demo_provider)
    else:
        providers.insert(0, demo_provider)
    if set_current or not data.get("current_id"):
        data["current_id"] = DEMO_PROVIDER_ID
        for provider in providers:
            provider["is_default"] = provider.get("id") == DEMO_PROVIDER_ID
    data["providers"] = providers
    save_providers(data)
    return data


def get_providers():
    data = load_json(PROVIDERS_FILE, DEFAULT_PROVIDERS_DATA)
    try:
        before = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        before = None
    data = _normalize_providers_data(data)
    if not data.get("providers"):
        data = _bootstrap_env_provider(data)
    if demo_mode_enabled():
        data = ensure_demo_provider(data, set_current=not data.get("current_id"))
    data = migrate_provider_secrets(data)
    try:
        after = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        after = ""
    if before is None or after != before:
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
        current["secret_storage"] = "runtime"
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
        provider["secret_storage"] = "runtime"
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
    if normalized_type in ("relay", "openai") and not normalized_base:
        errors.append("Relay/OpenAI 类型必须填写 Base URL。")
    if normalized_base and not re.match(r"^https?://", normalized_base):
        errors.append("Base URL 必须以 http:// 或 https:// 开头。")
    elif normalized_base:
        try:
            parsed_base_url = urllib.parse.urlsplit(normalized_base)
            hostname = parsed_base_url.hostname
        except ValueError:
            parsed_base_url = None
            hostname = None
        if not hostname:
            errors.append("Base URL 必须包含有效主机名。")
        elif parsed_base_url.username is not None or parsed_base_url.password is not None:
            errors.append("Base URL 不能包含用户名或密码。")
        if parsed_base_url and (parsed_base_url.query or parsed_base_url.fragment):
            errors.append("Base URL 不能包含查询参数或片段。")
    return errors


def provider_with_runtime_secret(provider: dict, api_key: str) -> dict:
    runtime_provider = copy.deepcopy(provider or {})
    runtime_provider["api_key"] = (api_key or "").strip()
    runtime_provider["secret_storage"] = "runtime"
    return runtime_provider


def prepare_provider_for_save(provider: dict, replacement_secret: str = ""):
    replacement_secret = (replacement_secret or "").strip()
    effective_secret = replacement_secret or resolve_provider_api_key(provider)
    errors = validate_provider_config(
        provider.get("name", ""),
        provider.get("provider_type", "gemini"),
        effective_secret,
        provider.get("base_url", ""),
    )
    if errors:
        return None, errors, False
    prepared = copy.deepcopy(provider)
    prepared["base_url"] = normalize_provider_base_url(
        prepared.get("provider_type", "gemini"),
        prepared.get("base_url", ""),
    )
    if replacement_secret:
        prepared, stored_securely = persist_provider_secret(
            prepared, replacement_secret
        )
        return prepared, [], stored_securely
    return prepared, [], False


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


@st.cache_resource(show_spinner=False)
def get_task_repository(database_path: str, legacy_json_path: str):
    return SqliteTaskStore(
        Path(database_path), legacy_json_path=Path(legacy_json_path)
    )


TASK_REPOSITORY = get_task_repository(str(TASK_DB_FILE), str(TASKS_FILE))


def _task_runner_id() -> str:
    runner_prefix = os.getenv("TULITE_RUNNER_ID", "").strip()
    if not runner_prefix:
        workspace_id = TASK_REPOSITORY.get_or_create_workspace_id()
        runner_prefix = f"local-{workspace_id}"
    return f"{runner_prefix}-{os.getpid()}-{uuid.uuid4().hex[:12]}"


_TASK_OWNER_LOCK = threading.RLock()


def _new_task_id():
    return hashlib.md5(
        f"task-{datetime.now().timestamp()}-{random.random()}".encode()
    ).hexdigest()[:12]


def get_session_owner_id() -> str:
    """Return the stable owner for this installation across tabs and restarts."""
    with _TASK_OWNER_LOCK:
        legacy_instance = load_json(INSTANCE_FILE, {"owner_id": ""})
        owner_id = TASK_REPOSITORY.get_or_create_workspace_id(
            (legacy_instance.get("owner_id") or "").strip()
        )
        if TASK_REPOSITORY.get_metadata("ownership_migration_version") != "1":
            if _migrate_legacy_instance_ownership(owner_id):
                TASK_REPOSITORY.set_metadata("ownership_migration_version", "1")
    if st.session_state.get("session_owner_id") != owner_id:
        st.session_state["session_owner_id"] = owner_id
    return owner_id


@synchronized_history_mutation
def _migrate_legacy_instance_ownership(owner_id: str) -> bool:
    def migrate_tasks(data):
        for task in data.get("tasks", []):
            task["owner_id"] = owner_id
        return data

    TASK_REPOSITORY.migrate(migrate_tasks)
    history = load_json(HISTORY_FILE, {"records": []})
    records = history.get("records", []) if isinstance(history, dict) else []
    changed = False
    for record in records:
        if isinstance(record, dict) and record.get("owner_id") != owner_id:
            record["owner_id"] = owner_id
            changed = True
    if changed:
        history["records"] = records
        return save_json(HISTORY_FILE, history)
    return True


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


def list_history_records(record_states=None, owner_id=None):
    # get_history_data() 已完成 normalize（含 deepcopy），此处不再重复
    data = get_history_data()
    records = list(data.get("records", []))
    if record_states:
        allowed_states = {
            str(state or "").strip().lower() for state in record_states if state
        }
        records = [r for r in records if r.get("record_state") in allowed_states]
    if owner_id is not None:
        # 历史遗留记录（无 owner_id）对所有会话可见；带 owner_id 的仅本人可见
        records = [
            r for r in records
            if not (r.get("owner_id") or "") or r.get("owner_id") == owner_id
        ]
    return sorted(records, key=_history_sort_key, reverse=True)


def list_active_history_records(owner_id=None):
    return list_history_records({HISTORY_RECORD_ACTIVE}, owner_id=owner_id)


def list_trashed_history_records(owner_id=None):
    return list_history_records({HISTORY_RECORD_TRASHED}, owner_id=owner_id)


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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in file_paths or []:
            if not path:
                continue
            src = Path(path)
            if src.exists():
                z.write(src, arcname=src.name)
        if titles:
            titles_content = format_titles_text(titles)
            z.writestr("titles.txt", titles_content)
        if errors:
            z.writestr("errors.txt", "\n".join([str(err) for err in errors if err]))
    return str(zip_path)


def _write_project_text_files(
    dest_dir: Path, titles: list, errors: list, target_language: str
):
    dest_dir.mkdir(parents=True, exist_ok=True)
    if titles:
        content = format_titles_text(titles)
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
    return create_task(record.get("task_type", "task"), payload)


def _record_task_history(task: dict, result: dict):
    if not task or task.get("status") not in TASK_TERMINAL_STATUSES:
        return None
    task_id = task.get("id") or _new_task_id()
    persisted_task = TASK_REPOSITORY.get(task_id)
    if persisted_task and persisted_task.get("history_archived_at"):
        return get_history_record(task_id)
    task = persisted_task or task
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
        "item_results": task.get("item_results", [])
        or result.get("item_results", []),
        "file_paths": copied_files,
        "input_file_paths": copied_input_paths,
        "zip_path": zip_path,
        "artifact_dir": str(artifact_dir),
        "project_name": artifact_dir.name,
        "provider_id": (task.get("payload", {}) or {}).get("provider_id", ""),
        "owner_id": task.get("owner_id", ""),
        "payload": payload_snapshot,
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = [r for r in data.get("records", []) if r.get("task_id") != task_id]
    records.append(manifest)
    pruned_records = []
    # Only purge records the user already moved to trash. Active project history
    # is durable user data even when the soft history limit is exceeded.
    if len(records) > MAX_HISTORY_RECORDS:
        overflow = len(records) - MAX_HISTORY_RECORDS
        pruned_records = [
            candidate
            for candidate in sorted(records, key=_history_sort_key)
            if (
                candidate.get("record_state") or HISTORY_RECORD_ACTIVE
            )
            == HISTORY_RECORD_TRASHED
            and candidate.get("task_id") != task_id
        ][:overflow]
        removed_ids = {candidate.get("task_id") for candidate in pruned_records}
        records = [r for r in records if r.get("task_id") not in removed_ids]
    data["records"] = records
    if not save_history_data(data):
        return None
    for candidate in pruned_records:
        candidate_dir = candidate.get("artifact_dir")
        if candidate_dir:
            shutil.rmtree(candidate_dir, ignore_errors=True)
    if persisted_task:
        TASK_REPOSITORY.update(
            task_id,
            {"history_archived_at": datetime.now().isoformat()},
            expected_status=task.get("status"),
        )
    return manifest


@synchronized_history_mutation
def record_task_history(task: dict, result: dict):
    try:
        return _record_task_history(task, result)
    except Exception:
        logger.exception("task history archiving failed (task_id=%s)", (task or {}).get("id"))
        return None


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
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


@synchronized_history_mutation
def purge_all_trashed_history_records():
    return purge_history_records_by_status(TASK_TERMINAL_STATUSES)


def format_bytes(num_bytes: int):
    value = float(num_bytes or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{int(num_bytes)} B"


_PATH_SIZE_CACHE = {}
_PATH_SIZE_CACHE_LOCK = threading.Lock()


def get_path_size(path: Path):
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    key = (str(path), mtime)
    with _PATH_SIZE_CACHE_LOCK:
        cached = _PATH_SIZE_CACHE.get(key)
    if cached is not None:
        return cached
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    with _PATH_SIZE_CACHE_LOCK:
        if len(_PATH_SIZE_CACHE) > 512:
            _PATH_SIZE_CACHE.clear()
        _PATH_SIZE_CACHE[key] = total
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
                <span class="template-preview-badge">适用页面: {esc(group_meta.get('page_label', '未定义'))}</span>
                <div class="template-preview-name">{esc(icon)} {esc(item.get('name', '未命名模板'))}</div>
                <div class="template-preview-desc">{esc(item.get('desc', '暂无说明'))}</div>
                <div class="template-preview-hint">用途提示: {esc(usage_note or '暂无用途说明')}</div>
                <div class="template-preview-hint">提示语: {esc(hint or '无')}</div>
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
                <div>{esc(item.get('icon', '📦'))}</div>
                <div class="template-preview-mini-name">{esc(item.get('name', '未命名模板'))}</div>
                <div class="template-preview-mini-meta">排序: {int(item.get('order', 1))}</div>
                <div class="template-preview-mini-meta">{'启用中' if item.get('enabled', True) else '已停用'}</div>
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="template-preview-shell">
            <div class="template-preview-title">{esc(group_meta.get('title', group_key))} 工作流预览</div>
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


def record_owned_by_session(record: dict) -> bool:
    """UI 层校验：记录无 owner_id（历史遗留）或属于当前会话时才可操作。"""
    rid = (record or {}).get("owner_id") or ""
    return (not rid) or rid == get_session_owner_id()


def render_batch_record_actions(records: list, mode: str):
    records = [r for r in records if record_owned_by_session(r)]
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
    image_templates = get_templates()

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
    return sorted(
        TASK_REPOSITORY.list(), key=lambda x: x.get("created_at", ""), reverse=True
    )


def list_tasks_for_display():
    """Query the current workspace's tasks at the storage seam."""
    owner_id = get_session_owner_id()
    return sorted(
        TASK_REPOSITORY.list(
            scope_owner_id=owner_id,
            include_unowned=True,
        ),
        key=lambda task: task.get("created_at", ""),
        reverse=True,
    )


def clear_completed_tasks():
    return TASK_REPOSITORY.clear_archived_done(
        scope_owner_id=get_session_owner_id(),
        include_unowned=True,
    )


def update_task(
    task_id: str,
    expected_status=None,
    expected_claim_token: str = None,
    scope_owner_id: str = None,
    include_unowned: bool = False,
    **updates,
):
    current = TASK_REPOSITORY.get(
        task_id,
        scope_owner_id=scope_owner_id,
        include_unowned=include_unowned,
    )
    if not current:
        return None
    now = datetime.now().isoformat()
    changes = copy.deepcopy(updates)
    changes["updated_at"] = now
    if changes.get("status") == "running" and not current.get("started_at"):
        changes["started_at"] = now
    if (
        changes.get("status") in TASK_TERMINAL_STATUSES
        and not current.get("ended_at")
    ):
        changes["ended_at"] = now
    return TASK_REPOSITORY.update(
        task_id,
        changes,
        expected_status=expected_status,
        expected_claim_token=expected_claim_token,
        scope_owner_id=scope_owner_id,
        include_unowned=include_unowned,
    )


def create_task(task_type: str, payload: dict):
    payload = copy.deepcopy(payload or {})
    if task_type == "smart" and not payload.get("retry_items"):
        payload.setdefault("compliance_user_id", get_user_id())
    handler = get_task_handlers().get(str(task_type or ""))
    validation_errors = (
        [f"不支持的任务类型：{task_type or 'unknown'}"]
        if not handler
        else [
            str(error)
            for error in handler.validate_payload(payload)
            if error
        ]
    )
    if validation_errors:
        return None, "；".join(validation_errors)
    _, max_task_queue = get_task_limits()
    now = datetime.now().isoformat()
    task = {
        "id": _new_task_id(),
        "type": task_type,
        "status": "queued",
        "owner_id": get_session_owner_id(),
        "created_at": now,
        "updated_at": now,
        "payload": copy.deepcopy(payload),
        "priority": int(payload.get("priority") or 0),
        "available_at": str(payload.get("available_at") or ""),
        "progress": {"done": 0, "total": payload.get("total", 0)},
        "errors": [],
        "titles": [],
        "result_files": [],
        "result_title_language": payload.get("target_language")
        or payload.get("title_language")
        or DEFAULT_TARGET_LANGUAGE,
        "summary": payload.get("summary", ""),
    }
    try:
        return (
            TASK_REPOSITORY.create(
                task,
                max_tasks=max_task_queue,
                terminal_statuses=TASK_TERMINAL_STATUSES,
            ),
            "",
        )
    except TaskCapacityError:
        return (
            None,
            f"最多同时保留 {max_task_queue} 个任务，请先清理已完成或失败任务。",
        )


def is_retryable_failed_item(item: dict, require_prompt: bool = True) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("status") != "error":
        return False
    if require_prompt and not item.get("prompt"):
        return False
    if item.get("retryable") is True:
        return True
    error_type = str(item.get("error_type") or "").lower()
    if error_type in RETRYABLE_IMAGE_ERROR_TYPES:
        return True
    return classify_image_task_error(item.get("error", "")).get("retryable") is True


def normalize_failed_item_retry_summary(summary: str) -> str:
    base = str(summary or "").strip()
    if not base.startswith(FAILED_ITEM_RETRY_SUMMARY_PREFIX):
        return base
    while base.startswith(FAILED_ITEM_RETRY_SUMMARY_PREFIX):
        base = base[len(FAILED_ITEM_RETRY_SUMMARY_PREFIX):].strip()
    return f"{FAILED_ITEM_RETRY_SUMMARY_PREFIX}{base or '智能组图'}"


def build_failed_item_retry_summary(summary: str, retry_total: int = 0) -> str:
    normalized = normalize_failed_item_retry_summary(summary or "智能组图")
    if retry_total:
        normalized = re.sub(r" · \d+张$", f" · {retry_total}张", normalized)
    if normalized.startswith(FAILED_ITEM_RETRY_SUMMARY_PREFIX):
        return normalized
    return f"{FAILED_ITEM_RETRY_SUMMARY_PREFIX}{normalized}"


def build_task_display_summary(task: dict) -> str:
    task = task or {}
    summary = normalize_failed_item_retry_summary(
        task.get("summary") or task.get("type", "任务")
    )
    payload = task.get("payload", {}) or {}
    if not payload.get("retry_parent_id"):
        return summary
    progress = task.get("progress", {}) or {}
    try:
        retry_total = int(progress.get("total") or payload.get("total") or 0)
    except (TypeError, ValueError):
        return summary
    if retry_total:
        return re.sub(r" · \d+张$", f" · {retry_total}张", summary)
    return summary


def get_combo_retry_request(task: dict, item: dict):
    stored_req = item.get("req")
    if isinstance(stored_req, dict):
        retry_req = copy.deepcopy(stored_req)
        try:
            batch_index = int(
                retry_req.get("_batch_index") or item.get("index") or 1
            )
        except (TypeError, ValueError):
            batch_index = 1
        retry_req["_batch_index"] = batch_index
        return retry_req

    try:
        batch_index = int(item.get("index") or 0)
    except (TypeError, ValueError):
        return None
    reqs = (task.get("payload", {}) or {}).get("reqs", []) or []
    if batch_index < 1 or batch_index > len(reqs):
        return None
    retry_req = copy.deepcopy(reqs[batch_index - 1])
    retry_req["_batch_index"] = batch_index
    return retry_req


def get_retryable_failed_items(task: dict) -> list:
    task_type = str((task or {}).get("type") or "")
    items = task.get("item_results", []) or []
    if task_type in {"", "smart"}:
        return [item for item in items if is_retryable_failed_item(item)]
    if task_type == "combo":
        return [
            item
            for item in items
            if is_retryable_failed_item(item, require_prompt=False)
            and get_combo_retry_request(task, item)
        ]
    return []


def build_failed_item_retry_payload(
    task: dict,
    provider_id: str = "",
    model: str = "",
):
    task_type = str((task or {}).get("type") or "")
    if task_type not in {"smart", "combo"}:
        return None, "仅智能组图和快速出图任务支持按失败项重试。"
    wait_seconds = failed_item_retry_wait_seconds(task)
    if wait_seconds:
        return None, f"上游仍在冷却，请等待 {wait_seconds} 秒后再重试失败项。"
    payload = copy.deepcopy(task.get("payload", {}) or {})
    retryable_items = get_retryable_failed_items(task)
    if task_type == "smart":
        failed_items = [
            {
                "type_name": item.get("type_name", "图片"),
                "index": item.get("index", index + 1),
                "prompt": item.get("prompt", ""),
            }
            for index, item in enumerate(retryable_items)
        ]
        if not failed_items:
            return None, "该任务没有可重试的失败项。"
        retry_fields = {
            "retry_items": failed_items,
            "total": len(failed_items),
        }
    else:
        failed_reqs = [
            retry_req
            for item in retryable_items
            for retry_req in [get_combo_retry_request(task, item)]
            if retry_req
        ]
        if not failed_reqs:
            return None, "该任务没有可重试的失败项。"
        retry_fields = {
            "reqs": failed_reqs,
            "total": len(failed_reqs),
        }
    payload.update(
        {
            **retry_fields,
            "retry_parent_id": task.get("id", ""),
            "enable_title": False,
            "title_info": "",
            "summary": build_failed_item_retry_summary(
                task.get("summary", ""),
                retry_fields["total"],
            ),
        }
    )
    if provider_id:
        payload["provider_id"] = provider_id
    if model:
        payload["model"] = model
    return payload, ""


def has_retryable_failed_items(task: dict) -> bool:
    return bool(get_retryable_failed_items(task))


def build_task_center_state(task: dict) -> dict:
    task = task or {}
    status = str(task.get("status") or "empty")
    return {
        "status": status,
        "can_cancel": status in {"queued", "running"},
        "can_retry_failed_items": (
            status in TASK_TERMINAL_STATUSES
            and has_retryable_failed_items(task)
        ),
    }


def build_task_timeout_diagnostic(task: dict) -> str:
    task = task or {}
    timeout_items = [
        item
        for item in (task.get("item_results", []) or [])
        if isinstance(item, dict)
        and item.get("status") == "error"
        and item.get("error_type") == "upstream_timeout"
    ]
    if not timeout_items:
        return ""
    elapsed_values = []
    for item in timeout_items:
        try:
            elapsed = float(item.get("elapsed_seconds"))
        except (TypeError, ValueError):
            continue
        if elapsed >= 0:
            elapsed_values.append(round(elapsed, 1))
    if not elapsed_values:
        try:
            started_at = datetime.fromisoformat(str(task.get("started_at") or ""))
            ended_at = datetime.fromisoformat(str(task.get("ended_at") or ""))
            elapsed_values.append(
                round(max(0.0, (ended_at - started_at).total_seconds()), 1)
            )
        except (TypeError, ValueError):
            return ""
    elapsed_text = (
        f"{elapsed_values[0]:.1f} 秒"
        if len(elapsed_values) == 1
        else f"{min(elapsed_values):.1f}–{max(elapsed_values):.1f} 秒"
    )
    local_timeout = float(GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS)
    ambiguity_margin = max(5.0, min(30.0, local_timeout * 0.02))
    if max(elapsed_values) >= local_timeout - ambiguity_margin:
        return (
            f"诊断：请求约 {elapsed_text}后结束，已接近本地等待上限 "
            f"{GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS} 秒；现有日志无法仅凭耗时判断"
            "是上游网关还是 TuLite 本地等待超时。"
        )
    return (
        f"诊断：请求在上游约 {elapsed_text}后结束；TuLite 本地等待上限为 "
        f"{GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS} 秒，因此不是本地等待超时。"
    )


def build_task_route_summary(task: dict) -> str:
    task = task or {}
    payload = task.get("payload", {}) or {}
    provider = get_provider_by_id(str(payload.get("provider_id") or "")) or {}
    provider_name = str(provider.get("name") or "未找到")
    model = str(payload.get("model") or provider.get("image_model") or "未配置")
    return (
        f"提供商：{provider_name} · 模型：{model} · "
        f"任务 ID：{task.get('id', '')}"
    )


def get_retry_image_providers() -> list:
    providers = []
    for saved_provider in get_providers().get("providers", []):
        if not saved_provider.get("enabled", True):
            continue
        provider = get_provider_by_id(saved_provider.get("id", ""))
        if provider and provider.get("api_key"):
            providers.append(provider)
    return providers


def retry_failed_task_items(
    task_id: str,
    provider_id: str = "",
    model: str = "",
):
    task = TASK_REPOSITORY.get(
        task_id,
        scope_owner_id=get_session_owner_id(),
        include_unowned=True,
    )
    if provider_id:
        provider = get_provider_by_id(provider_id)
        if (
            not provider
            or not provider.get("enabled", True)
            or not provider.get("api_key")
        ):
            return None, "所选重试提供商不可用，请检查启用状态和 API Key。"
        model = (model or provider.get("image_model") or "").strip()
        if not model:
            return None, "所选重试提供商尚未配置出图模型。"
    payload, error = build_failed_item_retry_payload(
        task,
        provider_id=provider_id,
        model=model,
    )
    if not payload:
        return None, error
    return create_task(task.get("type", "smart"), payload)


def cancel_task(task_id: str):
    owner_id = get_session_owner_id()
    current = TASK_REPOSITORY.get(
        task_id,
        scope_owner_id=owner_id,
        include_unowned=True,
    ) or {}
    errors = list(current.get("errors") or [])
    if "用户手动取消任务" not in errors:
        errors.append("用户手动取消任务")
    task = update_task(
        task_id,
        expected_status={"queued", "running"},
        scope_owner_id=owner_id,
        include_unowned=True,
        status="cancelled",
        errors=errors,
    )
    if task:
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
    return bool(task)


def repair_unarchived_task_history(limit: int = 3):
    pending = [
        task
        for task in list_tasks()
        if task.get("status") in TASK_TERMINAL_STATUSES
        and not task.get("history_archived_at")
    ]
    for task in sorted(pending, key=lambda item: item.get("updated_at", ""))[:limit]:
        record_task_history(
            task,
            {
                "titles": task.get("titles", []),
                "errors": task.get("errors", []),
                "files": task.get("result_files", []),
                "item_results": task.get("item_results", []),
                "target_language": task.get(
                    "result_title_language", DEFAULT_TARGET_LANGUAGE
                ),
            },
        )


def persist_image_for_task(img: Image.Image, filename: str):
    task_dir = DATA_DIR / "task_results"
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / filename
    img.save(path, format="PNG")
    return str(path)


class ReferenceImageLoadError(RuntimeError):
    pass


def load_image_paths(paths: list):
    images = []
    for raw_path in paths or []:
        display_name = Path(str(raw_path)).name or "未命名文件"
        try:
            with Image.open(raw_path) as source:
                source.load()
                images.append(source.convert("RGB"))
        except Exception as error:
            raise ReferenceImageLoadError(
                f"参考图无法读取：{display_name}。请重新上传后重试。"
            ) from error
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


def _demo_title_lines(product_info: str, target_language: str) -> list:
    base = re.sub(r"\s+", " ", (product_info or "Premium ecommerce product").strip())
    base = base[:80] or "Premium ecommerce product"
    english_titles = [
        f"{base} for Daily Use with Durable Build, Clean Modern Style, Easy Handling, Practical Storage, Gift Ready Packaging, and Reliable Value for Home, Office, Travel, and Online Marketplace Display",
        f"{base} Featuring Thoughtful Details, Smooth Finish, Versatile Everyday Performance, Clear Product Benefits, Lightweight Convenience, and Customer Friendly Presentation for Strong Listing Conversion",
        f"{base} Designed for Practical Shopping Needs with Organized Features, Attractive Visual Appeal, Simple Maintenance, Dependable Materials, and Marketplace Ready Descriptions for Ecommerce Growth",
    ]
    if target_language == "en":
        return english_titles
    language_info = get_target_language(target_language)
    localized = [
        f"{language_info['native_name']}演示标题：突出耐用材质、清晰卖点和日常使用场景，适合电商详情页展示。",
        f"{language_info['native_name']}演示标题：强调便捷体验、现代外观和高转化视觉信息，便于快速上架。",
        f"{language_info['native_name']}演示标题：覆盖规格、功能和礼品化包装，适合面试演示与内部评审。",
    ]
    lines = []
    for english, local in zip(english_titles, localized):
        lines.extend([english, local])
    return lines


def _demo_anchor(name: str = "", detail: str = "") -> dict:
    product_name = (name or detail or "Demo Product").strip()[:80] or "Demo Product"
    return {
        "product_name_en": product_name,
        "product_name_zh": product_name,
        "primary_category": "Demo Ecommerce Category",
        "visual_attrs": ["durable", "modern", "marketplace ready"],
        "confidence": 0.96,
    }


def _demo_requirements(anchor: dict, types_counts: dict, target_language: str) -> list:
    templates = get_template_group("combo_types")
    language_info = get_target_language(target_language)
    requirements = []
    for type_key, count in (types_counts or {}).items():
        info = templates.get(type_key, {})
        for index in range(int(count or 0)):
            requirements.append(
                {
                    "type_key": type_key,
                    "type_name": info.get("name", type_key),
                    "index": index + 1,
                    "topic": f"{info.get('name', type_key)}演示",
                    "scene": f"{anchor.get('product_name_zh', '商品')}的{info.get('desc', '电商展示')}场景",
                    "headline": f"{language_info['native_name']} Demo Highlight",
                    "subline": "Local admin demo output",
                    "badge": "DEMO",
                }
            )
    return requirements


def _demo_image(label: str, subtitle: str = "", aspect: str = "1:1") -> Image.Image:
    aspect_map = {
        "1:1": (960, 960),
        "4:3": (1024, 768),
        "3:4": (768, 1024),
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "3:2": (1080, 720),
        "2:3": (720, 1080),
        "4:5": (864, 1080),
        "5:4": (1080, 864),
        "21:9": (1344, 576),
    }
    width, height = aspect_map.get(aspect, (960, 960))
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    accent = "#6366f1"
    draw.rectangle([0, 0, width, int(height * 0.16)], fill=accent)
    draw.rectangle(
        [int(width * 0.08), int(height * 0.24), int(width * 0.92), int(height * 0.78)],
        fill="#ffffff",
        outline="#cbd5e1",
        width=4,
    )
    draw.ellipse(
        [int(width * 0.34), int(height * 0.34), int(width * 0.66), int(height * 0.66)],
        fill="#e0e7ff",
        outline=accent,
        width=5,
    )
    draw.text((int(width * 0.08), int(height * 0.055)), "Xiaobaitu Local Demo", fill="#ffffff")
    draw.text((int(width * 0.13), int(height * 0.42)), label[:42] or "Demo Output", fill="#0f172a")
    draw.text(
        (int(width * 0.13), int(height * 0.50)),
        (subtitle or "Generated without external API calls")[:58],
        fill="#475569",
    )
    draw.text((int(width * 0.13), int(height * 0.70)), "DEMO ADMIN MODE", fill=accent)
    return image


def get_compliance():
    def _build():
        c = load_json(COMPLIANCE_FILE, DEFAULT_COMPLIANCE)
        for k, v in DEFAULT_COMPLIANCE.items():
            if k not in c:
                c[k] = v
        return c

    return _cached_config(COMPLIANCE_FILE, _build)


def save_compliance(data):
    return save_json(COMPLIANCE_FILE, data)


def get_prompts():
    def _build():
        p = load_json(PROMPTS_FILE, DEFAULT_PROMPTS)
        for k, v in DEFAULT_PROMPTS.items():
            if k not in p:
                p[k] = v
        return p

    return _cached_config(PROMPTS_FILE, _build)


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
    def _build():
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

    return _cached_config(TITLE_TEMPLATES_FILE, _build)


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
    """语言选择器。

    - 图片语言（key_suffix 含 image）：按页面独立（per-prefix），每次任务单独选择，
      初始默认取设置里的 default_image_language，不回写全局。
    - 标题语言：保持跨页面共享 global_title_language 的旧行为。"""
    s = get_settings()
    options = [item["code"] for item in TARGET_LANGUAGES]
    is_image_lang = "image" in key_suffix
    state_key = f"{prefix}_{key_suffix}"

    if is_image_lang:
        # 每个页面独立的图片语言选择，不与其他页面/全局设置联动
        if state_key in st.session_state:
            current_code = st.session_state[state_key]
        else:
            current_code = s.get("default_image_language", DEFAULT_TARGET_LANGUAGE)
        if current_code not in options:
            current_code = DEFAULT_TARGET_LANGUAGE
        return st.selectbox(
            label,
            options=options,
            index=options.index(current_code),
            format_func=format_target_language_option,
            key=state_key,
            help=help_text,
        )

    global_key = "global_title_language"
    if global_key not in st.session_state:
        default_code = s.get("default_title_language", DEFAULT_TARGET_LANGUAGE)
        if default_code not in options:
            default_code = DEFAULT_TARGET_LANGUAGE
        st.session_state[global_key] = default_code

    current_code = st.session_state[global_key]
    if current_code not in options:
        current_code = DEFAULT_TARGET_LANGUAGE
    default_index = options.index(current_code)

    selected = st.selectbox(
        label,
        options=options,
        index=default_index,
        format_func=format_target_language_option,
        key=state_key,
        help=help_text,
    )
    st.session_state[global_key] = selected
    return selected


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
    prompts = get_prompts()
    if target_language == "en":
        rules_template = (
            prompts.get("title_language_rules_en")
            or DEFAULT_PROMPTS["title_language_rules_en"]
        )
        rules = fill_prompt_template(
            rules_template,
            min_title_en_chars=MIN_TITLE_EN_CHARS,
            max_title_en_chars=MAX_TITLE_EN_CHARS,
        )
        return f"{prompt}\n\n{rules}"

    extra_rule = (
        "Use Simplified Chinese for every translation line."
        if target_language == "zh"
        else f"Do not output Chinese. Use {lang['english_name']} only for every translation line."
    )
    rules_template = (
        prompts.get("title_language_rules_bilingual")
        or DEFAULT_PROMPTS["title_language_rules_bilingual"]
    )
    rules = fill_prompt_template(
        rules_template,
        target_language_name=lang["english_name"],
        target_language_native=lang["native_name"],
        translation_language_rule=extra_rule,
    )
    return f"{prompt}\n\n{rules}"


def build_temu_tri_title_prompt(template_prompt: str, product_info: str) -> str:
    """TEMU 三语标题提示词：中文/西语/法语三条标题，JSON 输出。

    所选标题模板仅作为产品类目背景参考注入，输出格式以三语规范为准。"""
    prompts = get_prompts()
    tri_template = (
        prompts.get("temu_tri_title_prompt")
        or DEFAULT_PROMPTS["temu_tri_title_prompt"]
    )
    template_context = ""
    if template_prompt:
        filled = fill_prompt_template(
            template_prompt,
            product_info=product_info,
            target_language_name="Spanish and French",
            target_language_native="Español / Français",
            target_language_label="西语/法语",
        )
        template_context = (
            "【类目模板参考（仅供理解产品与选词，其中关于输出语言/行数/格式的要求一律忽略，"
            "最终输出必须严格遵循本规范与 JSON 格式）】\n" + filled
        )
    return fill_prompt_template(
        tri_template,
        product_info=product_info or "No additional info provided",
        template_context=template_context,
    )


def get_image_language_instruction(target_language: str) -> str:
    lang = get_target_language(target_language)
    template = (
        get_prompts().get("image_language_instruction")
        or DEFAULT_PROMPTS["image_language_instruction"]
    )
    return fill_prompt_template(
        template,
        output_language_name=lang["english_name"],
        output_language_native=lang["native_name"],
        output_language_label=lang["label"],
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
def _matches_compliance_term(text_lower: str, term: str) -> bool:
    normalized_term = str(term or "").strip().lower()
    if not normalized_term:
        return False
    if normalized_term.isascii() and any(char.isalpha() for char in normalized_term):
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])",
                text_lower,
            )
        )
    return normalized_term in text_lower


def _find_concatenated_compliance_terms(text_lower: str, terms: set[str]) -> set[str]:
    latin_terms = [
        term for term in terms if term.isascii() and term.isalpha()
    ]
    matches = set()
    for prefix in latin_terms:
        for suffix in latin_terms:
            if f"{prefix}{suffix}" in text_lower:
                matches.update((prefix, suffix))
    return matches


def check_compliance(text, mode=None, user_id=None):
    if not text:
        return True, text, ""
    if mode is None:
        mode = st.session_state.get("user_compliance_mode", "strict")
    comp = get_compliance()
    preset = comp["presets"].get(mode, comp["presets"]["strict"])
    blacklist = set(w.lower() for w in preset.get("blacklist", []))
    blacklist.update(w.lower() for w in comp.get("custom_blacklist", []))
    uid = get_user_id() if user_id is None else str(user_id or "")
    user_custom = comp.get("user_custom", {}).get(uid, {})
    blacklist.update(w.lower() for w in user_custom.get("blacklist", []))
    whitelist = set(w.lower() for w in comp.get("whitelist", []))
    whitelist.update(w.lower() for w in user_custom.get("whitelist", []))
    text_lower = text.lower()
    issues = {
        word
        for word in blacklist
        if word not in whitelist and _matches_compliance_term(text_lower, word)
    }
    issues.update(
        word
        for word in _find_concatenated_compliance_terms(text_lower, blacklist)
        if word not in whitelist
    )
    if issues:
        return False, text, f"风险词: {', '.join(sorted(issues)[:5])}"
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


# ==================== TEMU 三语标题（中/西/法）====================
TRI_TITLE_LANGS = ("zh", "es", "fr")
TRI_TITLE_LABELS = {"zh": "中文", "es": "Español", "fr": "Français"}
TRI_TITLE_FLAGS = {"zh": "🇨🇳", "es": "🇪🇸", "fr": "🇫🇷"}
TRI_TITLE_MIN_CHARS = 150
TRI_TITLE_MAX_CHARS = 200
# 各语言标题建议字符区间：中文自然长度远短于西/法语，单独设区间
TITLE_CHAR_RANGES = {"zh": (40, 80), "es": (150, 200), "fr": (150, 200)}


def get_title_char_range(lang: str) -> tuple:
    return TITLE_CHAR_RANGES.get(lang, (TRI_TITLE_MIN_CHARS, TRI_TITLE_MAX_CHARS))


def parse_tri_language_titles(text: str) -> dict:
    """解析三语标题 JSON 输出，返回 {"entries": [...], "issues": [...]}。

    - 容忍 markdown 代码块包裹与 JSON 前后杂质
    - 字符数以 Python len() 为准，不信任模型自报数值
    """
    result = {"entries": [], "issues": []}
    if not text:
        return result
    cleaned = _strip_code_fence(text).strip()
    data = None
    for candidate in (cleaned,):
        try:
            data = json.loads(candidate)
            break
        except Exception:
            pass
    if data is None:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return result
    for item in data.get("titles", []) or []:
        if not isinstance(item, dict):
            continue
        lang = str(item.get("lang", "")).strip().lower()
        title = str(item.get("title", "") or "").strip()
        if lang not in TRI_TITLE_LANGS or not title:
            continue
        entry = {
            "lang": lang,
            "title": title,
            "chars": len(title),
        }
        back = str(item.get("back_translation_zh", "") or "").strip()
        if lang in ("es", "fr"):
            entry["back_translation_zh"] = back
        result["entries"].append(entry)
    for issue in data.get("issues", []) or []:
        issue_text = str(issue or "").strip()
        if issue_text:
            result["issues"].append(issue_text)
    return result


def _validate_tri_title_output(parsed: dict) -> tuple:
    """校验三语标题结果。允许例外规则：缺某语言时须在 issues 里有说明。"""
    entries = parsed.get("entries", []) if parsed else []
    issues = parsed.get("issues", []) if parsed else []
    details = {
        "langs": [e.get("lang") for e in entries],
        "issue_count": len(issues),
    }
    if not entries and not issues:
        return False, "未解析到任何标题（JSON 格式不符合要求）", details
    seen = set()
    for entry in entries:
        lang = entry.get("lang")
        if lang in seen:
            return False, f"语言 {lang} 出现重复标题", details
        seen.add(lang)
        if lang in ("es", "fr") and not entry.get("back_translation_zh"):
            return False, f"{TRI_TITLE_LABELS.get(lang, lang)} 标题缺少中文回译", details
    missing = [l for l in TRI_TITLE_LANGS if l not in seen]
    if missing and not issues:
        missing_labels = "、".join(TRI_TITLE_LABELS[l] for l in missing)
        return False, f"缺少 {missing_labels} 标题且无 issues 说明", details
    return True, "", details


def normalize_title_entries(titles: list) -> list:
    """把任务/历史里存储的标题统一为 dict 条目列表；兼容旧版纯字符串。"""
    entries = []
    for item in titles or []:
        if isinstance(item, dict):
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            entry = dict(item)
            entry["title"] = title
            entry["chars"] = len(title)
            entries.append(entry)
        elif isinstance(item, str) and item.strip():
            entries.append({"lang": "", "title": item.strip(), "chars": len(item.strip())})
    return entries


def format_titles_text(titles: list, issues: list = None) -> str:
    """标题内容的纯文本布局（用于复制区、titles.txt、历史展示）。"""
    entries = normalize_title_entries(titles)
    lines = []
    idx = 0
    issue_lines = [f"⚠️ {issue}" for issue in issues or []]
    for entry in entries:
        lang = entry.get("lang", "")
        if lang == "issue":
            issue_lines.append(f"⚠️ {entry['title']}")
            continue
        idx += 1
        label = TRI_TITLE_LABELS.get(lang, lang or "标题")
        lines.append(f"{idx}. {label} — {entry['title']} | {entry['chars']}字符")
        back = entry.get("back_translation_zh", "")
        if back:
            lines.append(f"   中文回译: {back}")
    lines.extend(issue_lines)
    return "\n".join(lines)


def merge_titles_and_issues(title_result: dict) -> list:
    """把标题条目与 issues 合并成一个可持久化的列表（issues 作为特殊条目）。"""
    merged = list(title_result.get("titles", []) or [])
    for issue in title_result.get("issues", []) or []:
        merged.append({"lang": "issue", "title": str(issue)})
    return merged


def _demo_tri_title_entries(product_info: str) -> dict:
    base = re.sub(r"\s+", " ", (product_info or "演示商品").strip())[:40] or "演示商品"
    filler_zh = "多功能家用收纳系列 大容量分层设计 加厚耐用材质 卧室客厅浴室通用 简约现代风格 日常整理好帮手 适合家庭办公室出租屋多场景使用 灰白色"
    filler_es = "Organizador multifuncional para el hogar, gran capacidad con diseño de niveles, material grueso y duradero, ideal para dormitorio salón y baño, estilo moderno sencillo, color gris y blanco para uso diario"
    filler_fr = "Organisateur multifonction pour la maison, grande capacité avec design à niveaux, matériau épais et durable, idéal pour chambre salon et salle de bain, style moderne simple, coloris gris et blanc"
    entries = [
        {"lang": "zh", "title": f"{base} {filler_zh}"},
        {
            "lang": "es",
            "title": filler_es,
            "back_translation_zh": "多功能家用收纳架，大容量分层设计，加厚耐用材质，适合卧室客厅浴室，现代简约风格，灰白色，日常使用。",
        },
        {
            "lang": "fr",
            "title": filler_fr,
            "back_translation_zh": "多功能家用收纳架，大容量分层设计，加厚耐用材质，适合卧室客厅浴室，现代简约风格，灰白色。",
        },
    ]
    for entry in entries:
        entry["chars"] = len(entry["title"])
    return {"entries": entries, "issues": []}


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
    issues: list = None,
):
    return {
        "success": success,
        "titles": titles or [],
        "issues": issues or [],
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
    if "insufficient" in msg and ("balance" in msg or "quota" in msg or "余额" in msg):
        return "provider_error", False
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


def _redact_sensitive_error_text(message: str, secrets=()) -> str:
    redacted = _html_mod.unescape(str(message or ""))
    redacted = re.sub(r"<[^>]*>", " ", redacted)

    def redact_url(match):
        try:
            parsed = urllib.parse.urlsplit(match.group(0))
            hostname = parsed.hostname
            parsed.port
        except ValueError:
            return "[REDACTED_URL]"
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            return "[REDACTED_URL]"
        netloc = parsed.netloc.rsplit("@", 1)[-1]
        return urllib.parse.urlunsplit(
            (parsed.scheme, netloc, parsed.path, "", "")
        )

    redacted = re.sub(r"https?://[^\s<>\"']+", redact_url, redacted)
    redacted = re.sub(
        r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[^\s<>\"']+",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\bsk-[A-Za-z0-9_-]{8,}", "[REDACTED]", redacted
    )
    redacted = re.sub(
        r"(?i)(api[-_ ]?key\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
    )
    for secret in secrets or ():
        if secret:
            redacted = redacted.replace(str(secret), "[REDACTED]")
    return re.sub(r"\s+", " ", redacted).strip()


def sanitize_task_error(
    message: str,
    fallback: str = "任务执行失败",
    secrets=(),
) -> str:
    msg = str(message or "").strip()
    if not msg:
        return fallback
    low = msg.lower()
    if (
        "insufficient_balance" in low
        or "insufficient account balance" in low
        or ("insufficient" in low and ("balance" in low or "quota" in low))
    ):
        return "提供商账户余额不足，请充值后重试。"
    if "content_policy" in low or "content policy" in low or "moderation" in low:
        return "内容触发上游安全策略，请调整提示词或图片后重试。"
    if "too many requests" in low or "rate limit" in low:
        return "请求过于频繁，请稍后重试或降低并发任务数。"
    if "failed_precondition" in low or "user location is not supported" in low:
        return "Google API 当前账号或地区不支持该调用。"
    if "resource has been exhausted" in low or "proxy_config_error" in low:
        return "中转站上游配额已用尽，请稍后重试或切换其他模型/提供商。"
    if (
        "timeout" in low
        or "timed out" in low
        or "time-out" in low
        or "gateway timeout" in low
        or "gateway time-out" in low
        or re.search(r"\b50[234]\b", low)
    ):
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
    return _redact_sensitive_error_text(msg, secrets)[:180] or fallback


def format_task_error_summary(errors, limit: int = 3) -> str:
    return "; ".join(
        sanitize_task_error(error)
        for error in list(errors or [])[: max(0, int(limit))]
    )


def _image_retry_result(error: str, error_type: str, current: datetime) -> dict:
    return {
        "error": error,
        "error_type": error_type,
        "retryable": True,
        "retry_after_at": (
            current + timedelta(seconds=IMAGE_RETRY_COOLDOWN_SECONDS)
        ).isoformat(),
    }


def classify_image_task_error(message: str, now: datetime = None) -> dict:
    raw = str(message or "")
    low = raw.lower()
    current = now or datetime.now()
    is_upstream_timeout = bool(
        "timeout" in low
        or "timed out" in low
        or "time-out" in low
        or "gateway timeout" in low
        or "gateway time-out" in low
        or "请求超时" in raw
        or re.search(r"\b50[234]\b", low)
    )
    if is_upstream_timeout:
        return _image_retry_result(
            "上游图片生成超时或网关异常（502/503/504），成功图片已保留。请稍后仅重试失败项。",
            "upstream_timeout",
            current,
        )
    is_provider_connection = bool(
        "connection" in low
        or "connect" in low
        or "dns" in low
        or "refused" in low
        or "unreachable" in low
        or "提供商连接失败" in raw
        or "网络连接失败" in raw
    )
    if is_provider_connection:
        return _image_retry_result(
            "提供商连接失败，成功图片已保留。请稍后仅重试失败项。",
            "provider_connection",
            current,
        )
    if (
        "too many requests" in low
        or "rate limit" in low
        or "429" in low
        or "请求过于频繁" in raw
    ):
        return _image_retry_result(
            "上游请求过于频繁，成功图片已保留。请稍后仅重试失败项。",
            "rate_limited",
            current,
        )
    return {
        "error": sanitize_task_error(raw),
        "error_type": "upstream_error",
        "retryable": False,
        "retry_after_at": "",
    }


def classify_provider_image_task_error(message: str, provider: dict) -> dict:
    result = classify_image_task_error(message)
    result["error"] = sanitize_task_error(
        result.get("error", ""),
        secrets=(str((provider or {}).get("api_key") or ""),),
    )
    return result


def _classify_local_image_task_error(
    message: str,
    error_type: str,
    fallback: str,
    provider: dict,
) -> dict:
    error = _redact_sensitive_error_text(
        message,
        secrets=(str((provider or {}).get("api_key") or ""),),
    )[:180]
    return {
        "error": error or fallback,
        "error_type": error_type,
        "retryable": False,
        "retry_after_at": "",
    }


def failed_item_retry_wait_seconds(task: dict, now: datetime = None) -> int:
    current = now or datetime.now()
    waits = []
    for item in get_retryable_failed_items(task):
        retry_after_at = item.get("retry_after_at", "")
        if not retry_after_at:
            task_failed_at = task.get("ended_at") or task.get("updated_at") or ""
            try:
                retry_after_at = (
                    datetime.fromisoformat(task_failed_at)
                    + timedelta(seconds=IMAGE_RETRY_COOLDOWN_SECONDS)
                ).isoformat()
            except (TypeError, ValueError):
                retry_after_at = ""
        if not retry_after_at:
            continue
        try:
            remaining = (datetime.fromisoformat(retry_after_at) - current).total_seconds()
        except (TypeError, ValueError):
            continue
        if remaining > 0:
            waits.append(int(remaining + 0.999))
    return max(waits, default=0)


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

    def _sanitize_client_error(self, message: str) -> str:
        return sanitize_task_error(message, secrets=(self.api_key,))

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
                raw_error = str(e)
                self.last_error = self._sanitize_client_error(raw_error)
                err = raw_error.lower()
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
                raise Exception(self.last_error)
        raise Exception(self._sanitize_client_error(self.last_error or "请求失败"))

    def _prep_images(self, images, max_count=3):
        parts = []
        for img in images[:max_count]:
            buf = io.BytesIO()
            ic = img.copy()
            if max(ic.size) > 1024:
                limit_image_size(ic, (1024, 1024))
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
                limit_image_size(ic, (1024, 1024))
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
        endpoint = f"{self.base_url.rstrip('/')}/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            self.last_error = self._sanitize_client_error(body or str(e))
            raise Exception(self.last_error)
        except Exception as e:
            self.last_error = self._sanitize_client_error(str(e))
            raise Exception(self.last_error)

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
        return self._sanitize_client_error(self.last_error)

    def _text_request(
        self, prompt_text, timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS
    ):
        """纯文本生成（标题/图需/文案），子类可覆写为其他协议。"""
        resp = self._call(
            lambda: self.client.models.generate_content(
                model=self.title_model,
                contents=[prompt_text],
                config=types.GenerateContentConfig(response_modalities=["TEXT"]),
            ),
            timeout_seconds=timeout_seconds,
        )
        self._count_tokens(resp)
        return (resp.text or "").strip()

    def _vision_request(
        self,
        images,
        prompt_text,
        max_images=5,
        timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
    ):
        """图片+文本理解（商品分析/图片标题），子类可覆写为其他协议。"""
        if self.base_url:
            response_data = self._manual_generate_content(
                self.vision_model,
                self._prep_inline_image_parts(images, max_images)
                + [{"text": prompt_text}],
                ["TEXT"],
                timeout_seconds=timeout_seconds,
            )
            self._count_manual_tokens(response_data)
            return self._extract_text_from_manual_response(response_data)
        resp = self._call(
            lambda: self.client.models.generate_content(
                model=self.vision_model,
                contents=self._prep_images(images, max_images) + [prompt_text],
                config=types.GenerateContentConfig(response_modalities=["TEXT"]),
            ),
            timeout_seconds=timeout_seconds,
        )
        self._count_tokens(resp)
        return (resp.text or "").strip()

    def test_connection(self):
        """连通性测试：返回上游模型的简短回复。"""
        return self._text_request("Return exactly OK.")

    def analyze_product(self, images, name="", detail=""):
        default_result = {
            "product_name_en": name or "Product",
            "product_name_zh": name or "商品",
            "primary_category": "General",
            "visual_attrs": ["quality", "design"],
            "confidence": 0.5,
        }

        if is_demo_api_key(self.api_key):
            return _demo_anchor(name, detail)

        if not images:
            return default_result

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

        try:
            text = self._vision_request(images, prompt, 5)

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
        if is_demo_api_key(self.api_key):
            return _demo_requirements(anchor, types_counts, target_language)

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
            text = self._text_request(prompt)
            result = self._parse_json_response(text or "[]", [])
            return result if isinstance(result, list) else []
        except Exception as e:
            self.last_error = str(e)
            return []

    def generate_en_copy(self, anchor, requirements, target_language="zh"):
        if is_demo_api_key(self.api_key):
            language_info = get_target_language(target_language)
            for req in requirements or []:
                req.setdefault("headline", f"{language_info['native_name']} Demo Highlight")
                req.setdefault("subline", "Local admin demo output")
                req.setdefault("badge", "DEMO")
            return requirements

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
            text = self._text_request(prompt)

            copies = self._parse_json_response(text or "[]", [])
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
        if is_demo_api_key(self.api_key):
            label = "演示生成图"
            prompt_text = re.sub(r"\s+", " ", (prompt or "").strip())
            if prompt_text:
                label = prompt_text[:42]
            self.total_tokens += 128
            return _demo_image(label, get_image_language_instruction(text_language), aspect)

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
        # target_language 参数保留以兼容旧调用，三语标题固定输出 中文/西语/法语
        if is_demo_api_key(self.api_key):
            demo = _demo_tri_title_entries(product_info)
            return _build_title_result(
                True,
                titles=demo["entries"],
                raw_text=format_titles_text(demo["entries"]),
                attempt_count=1,
                input_mode="text",
                details={"demo": True},
                issues=demo["issues"],
            )

        if not self.api_key:
            return _build_title_result(
                False,
                error_type="missing_api_key",
                error_message="API Key未配置",
                retryable=False,
                attempt_count=0,
                input_mode="text",
            )

        prompt = build_temu_tri_title_prompt(template_prompt, product_info)
        last_raw = ""
        last_parsed = {"entries": [], "issues": []}
        for attempt in range(1, 3):
            try:
                prompt_text = prompt
                if attempt == 2:
                    prompt_text = (
                        f"{prompt}\n\nSTRICT OUTPUT: 只输出规范中的 JSON 对象本身，"
                        "不要 markdown 代码块，不要任何解释文字。"
                    )
                text = self._text_request(prompt_text)
                parsed = parse_tri_language_titles(text)
                valid, reason, details = _validate_tri_title_output(parsed)
                if valid:
                    return _build_title_result(
                        True,
                        titles=parsed["entries"],
                        raw_text=text,
                        attempt_count=attempt,
                        input_mode="text",
                        details=details,
                        issues=parsed["issues"],
                    )

                last_raw = text
                last_parsed = parsed
                if attempt == 1:
                    continue
                return _build_title_result(
                    False,
                    titles=parsed["entries"],
                    raw_text=text,
                    error_type="retry_exhausted",
                    error_message=reason or "输出格式不符合要求",
                    retryable=False,
                    attempt_count=attempt,
                    input_mode="text",
                    details=details,
                    issues=parsed["issues"],
                )
            except Exception as e:
                self.last_error = str(e)
                error_type, retryable = _classify_title_error(str(e))
                if error_type == "upstream_error" and self.base_url:
                    error_type = "provider_error"
                return _build_title_result(
                    False,
                    titles=last_parsed["entries"],
                    raw_text=last_raw,
                    error_type=error_type,
                    error_message=str(e),
                    retryable=retryable,
                    attempt_count=attempt,
                    input_mode="text",
                )

        return _build_title_result(
            False,
            titles=last_parsed["entries"],
            raw_text=last_raw,
            error_type="invalid_format",
            error_message="输出格式不符合要求",
            retryable=False,
            attempt_count=2,
            input_mode="text",
        )

    def generate_titles_from_image(
        self,
        images,
        product_info="",
        template_prompt=None,
        target_language="zh",
    ):
        """从图片分析生成商品标题（三语：中文/西语/法语）"""
        if is_demo_api_key(self.api_key):
            demo = _demo_tri_title_entries(product_info or "Image based product")
            return _build_title_result(
                True,
                titles=demo["entries"],
                raw_text=format_titles_text(demo["entries"]),
                attempt_count=1,
                input_mode="image",
                details={"demo": True},
                issues=demo["issues"],
            )

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

        if template_prompt is None:
            template_prompt = ""

        prompt = build_temu_tri_title_prompt(
            template_prompt,
            product_info or "No additional info provided",
        )

        last_raw = ""
        last_parsed = {"entries": [], "issues": []}
        for attempt in range(1, 3):
            try:
                prompt_text = prompt
                if attempt == 2:
                    prompt_text = (
                        f"{prompt}\n\nSTRICT OUTPUT: 只输出规范中的 JSON 对象本身，"
                        "不要 markdown 代码块，不要任何解释文字。"
                    )
                text = self._vision_request(images, prompt_text, 5)
                parsed = parse_tri_language_titles(text)
                valid, reason, details = _validate_tri_title_output(parsed)
                if valid:
                    return _build_title_result(
                        True,
                        titles=parsed["entries"],
                        raw_text=text,
                        attempt_count=attempt,
                        input_mode="image",
                        details=details,
                        issues=parsed["issues"],
                    )

                last_raw = text
                last_parsed = parsed
                if attempt == 1:
                    continue
                return _build_title_result(
                    False,
                    titles=parsed["entries"],
                    raw_text=text,
                    error_type="retry_exhausted",
                    error_message=reason or "输出格式不符合要求",
                    retryable=False,
                    attempt_count=attempt,
                    input_mode="image",
                    details=details,
                    issues=parsed["issues"],
                )
            except Exception as e:
                self.last_error = str(e)
                error_type, retryable = _classify_title_error(str(e))
                if error_type == "upstream_error" and self.base_url:
                    error_type = "provider_error"
                return _build_title_result(
                    False,
                    titles=last_parsed["entries"],
                    raw_text=last_raw,
                    error_type=error_type,
                    error_message=str(e),
                    retryable=retryable,
                    attempt_count=attempt,
                    input_mode="image",
                )

        return _build_title_result(
            False,
            titles=last_parsed["entries"],
            raw_text=last_raw,
            error_type="invalid_format",
            error_message="输出格式不符合要求",
            retryable=False,
            attempt_count=2,
            input_mode="image",
        )



# ==================== OpenAI 兼容客户端 (GPT Image 2) ====================
class OpenAIClient(GeminiClient):
    """OpenAI 兼容协议客户端：
    出图走 /v1/images/generations 与 /v1/images/edits（GPT Image 2 等），
    标题/视觉走 /v1/chat/completions。"""

    def __init__(
        self,
        api_key,
        model="",
        base_url="",
        title_model="",
        vision_model="",
    ):
        self.api_key = api_key
        self.model = (model or "").strip() or OPENAI_DEFAULT_IMAGE_MODEL
        self.base_url = normalize_provider_base_url(
            "openai",
            (base_url or "").strip() or OPENAI_DEFAULT_BASE_URL,
        ).rstrip("/")
        self.title_model = (title_model or "").strip() or OPENAI_DEFAULT_TEXT_MODEL
        self.vision_model = (vision_model or "").strip() or self.title_model
        self.client = None
        self.prompts = self._load_prompts_safe()
        self.total_tokens = 0
        self.last_error = None

    # ---- 基础 HTTP ----
    @staticmethod
    def _extract_error_message(body: str) -> str:
        try:
            data = json.loads(body)
        except Exception:
            data = None
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("code") or "")[:300]
            if isinstance(err, str) and err:
                return err[:300]
            msg = data.get("message") or data.get("code")
            if msg:
                return str(msg)[:300]
        return (body or "")[:300]

    def _openai_call(
        self,
        path,
        payload=None,
        multipart=None,
        timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
        retries=3,
    ):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if multipart is not None:
            body, content_type = multipart
            headers["Content-Type"] = content_type
        else:
            body = json.dumps(payload or {}).encode("utf-8")
            headers["Content-Type"] = "application/json"
        delay = 2
        for attempt in range(max(1, retries)):
            req = urllib.request.Request(
                f"{self.base_url}{path}", data=body, headers=headers
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8", "ignore"))
            except urllib.error.HTTPError as e:
                detail = self._extract_error_message(
                    e.read().decode("utf-8", "ignore")
                )
                low = (detail or "").lower()
                self.last_error = self._sanitize_client_error(
                    detail or f"HTTP {e.code}"
                )
                if e.code == 401:
                    raise Exception("API Key 无效或未配置")
                if e.code == 403:
                    raise Exception(
                        "提供商拒绝访问该模型或接口，请检查模型权限和接口地址"
                    )
                if e.code == 402 or (
                    "insufficient" in low and ("balance" in low or "quota" in low)
                ):
                    raise Exception("提供商账户余额不足，请充值后重试")
                if (
                    "content_policy" in low
                    or "content policy" in low
                    or "moderation" in low
                ):
                    raise Exception(self.last_error)
                if (e.code == 429 or e.code >= 500) and attempt < retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise Exception(self.last_error)
            except Exception as e:
                err_text = str(e)
                self.last_error = self._sanitize_client_error(err_text)
                low = err_text.lower()
                retryable = (
                    "timed out" in low
                    or "timeout" in low
                    or "connection" in low
                    or "unreachable" in low
                    or "reset" in low
                )
                if retryable and attempt < retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                if "timed out" in low or "timeout" in low:
                    raise Exception(f"请求超时（{timeout_seconds}s），请稍后重试")
                raise Exception(self.last_error)
        raise Exception(self._sanitize_client_error(self.last_error or "请求失败"))

    # ---- 文本 / 视觉 ----
    def _chat(
        self, model, messages, timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS
    ):
        data = self._openai_call(
            "/chat/completions",
            {"model": model, "messages": messages},
            timeout_seconds=timeout_seconds,
        )
        usage = (data or {}).get("usage") or {}
        try:
            self.total_tokens += int(usage.get("total_tokens") or 0)
        except Exception:
            pass
        try:
            content = (data.get("choices") or [])[0].get("message", {}).get(
                "content", ""
            )
        except Exception:
            content = ""
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )
        return (content or "").strip()

    def _image_data_urls(self, images, max_count=5):
        urls = []
        for img in images[:max_count]:
            buf = io.BytesIO()
            ic = img.copy()
            if max(ic.size) > 1024:
                limit_image_size(ic, (1024, 1024))
            ic.save(buf, format="PNG", optimize=True)
            urls.append(
                "data:image/png;base64,"
                + base64.b64encode(buf.getvalue()).decode()
            )
        return urls

    def _text_request(
        self, prompt_text, timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS
    ):
        return self._chat(
            self.title_model,
            [{"role": "user", "content": prompt_text}],
            timeout_seconds=timeout_seconds,
        )

    def _vision_request(
        self,
        images,
        prompt_text,
        max_images=5,
        timeout_seconds=GEMINI_TEXT_REQUEST_TIMEOUT_SECONDS,
    ):
        content = [{"type": "text", "text": prompt_text}]
        for url in self._image_data_urls(images, max_images):
            content.append({"type": "image_url", "image_url": {"url": url}})
        return self._chat(
            self.vision_model,
            [{"role": "user", "content": content}],
            timeout_seconds=timeout_seconds,
        )

    # ---- 出图 ----
    @staticmethod
    def _map_openai_size(aspect):
        try:
            w, h = str(aspect).split(":")
            ratio = float(w) / float(h)
        except Exception:
            ratio = 1.0
        if ratio >= 1.15:
            return "1536x1024"
        if ratio <= 0.87:
            return "1024x1536"
        return "1024x1024"

    @staticmethod
    def _encode_ref_png(img, limit=2048):
        buf = io.BytesIO()
        ic = img.copy()
        if max(ic.size) > limit:
            limit_image_size(ic, (limit, limit))
        ic.save(buf, format="PNG")
        return buf.getvalue()

    def _images_edits(self, prompt, refs, size, quality):
        boundary = "----xiaobaitu" + hashlib.md5(
            f"{time.time()}{random.random()}".encode()
        ).hexdigest()[:16]
        chunks = []

        def add_field(name, value):
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        add_field("model", self.model)
        add_field("prompt", prompt)
        add_field("size", size)
        add_field("quality", quality)
        add_field("n", "1")
        for i, img in enumerate(refs):
            payload = self._encode_ref_png(img)
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="image[]"; '
                    f'filename="ref_{i}.png"\r\n'
                    "Content-Type: image/png\r\n\r\n"
                ).encode("utf-8")
                + payload
                + b"\r\n"
            )
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return self._openai_call(
            "/images/edits",
            multipart=(
                b"".join(chunks),
                f"multipart/form-data; boundary={boundary}",
            ),
            timeout_seconds=GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS,
            retries=1,
        )

    def _extract_openai_image(self, data):
        for item in (data or {}).get("data") or []:
            if not isinstance(item, dict):
                continue
            b64 = item.get("b64_json")
            if b64:
                try:
                    return Image.open(io.BytesIO(base64.b64decode(b64)))
                except Exception:
                    continue
            url = item.get("url")
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=60) as resp:
                        return Image.open(io.BytesIO(resp.read()))
                except Exception:
                    continue
        return None

    def generate_image(
        self,
        refs,
        prompt,
        aspect="1:1",
        size="1K",
        thinking_level="high",
        text_language="zh",
    ):
        if is_demo_api_key(self.api_key):
            label = "演示生成图"
            prompt_text = re.sub(r"\s+", " ", (prompt or "").strip())
            if prompt_text:
                label = prompt_text[:42]
            self.total_tokens += 128
            return _demo_image(
                label, get_image_language_instruction(text_language), aspect
            )

        full_prompt = (
            f"CRITICAL: {get_image_language_instruction(text_language)}\n\n"
            f"Target aspect ratio: {aspect}.\n\n"
            f"{prompt}"
        )
        quality = {"1K": "medium", "2K": "high", "4K": "high"}.get(size, "medium")
        target_size = self._map_openai_size(aspect)
        max_refs = MODELS.get(self.model, {}).get("max_refs", 10)
        try:
            if refs:
                data = self._images_edits(
                    full_prompt, refs[:max_refs], target_size, quality
                )
            else:
                data = self._openai_call(
                    "/images/generations",
                    {
                        "model": self.model,
                        "prompt": full_prompt,
                        "size": target_size,
                        "quality": quality,
                        "n": 1,
                    },
                    timeout_seconds=GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS,
                    retries=1,
                )
            usage = (data or {}).get("usage") or {}
            try:
                self.total_tokens += int(usage.get("total_tokens") or 0)
            except Exception:
                pass
            image = self._extract_openai_image(data)
            if image:
                return image
            self.last_error = "API返回无图片数据"
            return None
        except Exception as e:
            self.last_error = str(e)
            raise


def create_ai_client(provider, model="", title_model=None, vision_model=None):
    """按提供商类型构建客户端：gemini/relay → Gemini 协议，openai → OpenAI 协议。

    title_model/vision_model 为可选覆盖参数：不传（None）时沿用 provider 自身配置的值，
    传入非 None 值（例如用户在标题模型选择器里选中的模型名）时覆盖 provider 默认值。
    """
    provider = provider or {}
    provider_type = (provider.get("provider_type") or "gemini").strip().lower()
    image_model = (model or provider.get("image_model") or "").strip()
    resolved_title_model = (
        title_model if title_model is not None else provider.get("title_model", "")
    )
    resolved_vision_model = (
        vision_model if vision_model is not None else provider.get("vision_model", "")
    )
    common = dict(
        base_url=provider.get("base_url", ""),
        title_model=resolved_title_model,
        vision_model=resolved_vision_model,
    )
    if provider_type == "openai":
        return OpenAIClient(provider.get("api_key", ""), image_model, **common)
    return GeminiClient(provider.get("api_key", ""), image_model, **common)


# ==================== 图片尺寸限制工具 ====================
def limit_image_size(img: Image.Image, max_size=(1024, 1024), resample=Image.Resampling.LANCZOS) -> Image.Image:
    """Resize `img` in place (mutating and returning it) so neither dimension
    exceeds max_size, using .thumbnail() (preserves aspect ratio, no-op if
    already within bounds). Single consolidated entry point for the various
    ad-hoc `.thumbnail()` call sites in this file."""
    img.thumbnail(max_size, resample)
    return img


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
            if isinstance(img, str):
                # 支持磁盘路径形式的结果，避免在内存中长期持有 PIL 对象
                try:
                    z.writestr(filename, Path(img).read_bytes())
                except Exception:
                    pass
            elif img:
                img_buf = io.BytesIO()
                img.save(img_buf, format="PNG")
                z.writestr(filename, img_buf.getvalue())

        if titles:
            titles_content = format_titles_text(titles)
            z.writestr("titles.txt", titles_content)

    return buf.getvalue()


# ==================== 样式 ====================
def apply_style():
    st.markdown(
        """<style>
    :root { color-scheme: light; --primary: #1B2A4A; --accent: #FF7A45; --slate: #64748B; --success: #10b981; --warning: #f59e0b; --danger: #ef4444; }
    .main-title { font-size: 2.5rem; font-weight: 800; text-align: center; margin: 1rem 0; color: #1B2A4A; }
    .page-title { font-size: 1.75rem; font-weight: 700; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 3px solid var(--primary); }
    .stButton>button { border-radius: 10px; font-weight: 600; transition: all 0.2s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(27, 42, 74, 0.25); }
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
    #MainMenu, footer { visibility: hidden; }
    header { visibility: visible; background: transparent; }
    .title-box { background: linear-gradient(135deg, #eff6ff 0%, #f5f3ff 100%); border: 1px solid #c7d2fe; border-radius: 12px; padding: 1rem; margin: 0.75rem 0; }
    .image-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.5rem; margin: 0.5rem 0; background: white; }
    .image-label { font-size: 12px; font-weight: 600; color: #1B2A4A; text-align: center; margin-top: 0.25rem; }
    .template-preview-shell { border: 1px solid #dbe4f0; border-radius: 16px; background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%); padding: 1rem; margin: 0.5rem 0 1rem 0; }
    .template-preview-title { font-size: 13px; font-weight: 700; color: #1B2A4A; margin-bottom: 0.4rem; }
    .template-preview-subtitle { font-size: 12px; color: #64748b; margin-bottom: 0.75rem; }
    .template-preview-card { border: 1px solid #dbe4f0; border-radius: 14px; background: white; padding: 0.9rem; min-height: 128px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05); }
    .template-preview-card.disabled { opacity: 0.55; border-style: dashed; }
    .template-preview-badge { display: inline-block; border-radius: 999px; background: #f1f5f9; color: #1B2A4A; padding: 0.16rem 0.55rem; font-size: 11px; font-weight: 600; margin-right: 0.35rem; }
    .template-preview-badge.off { background: #f3f4f6; color: #6b7280; }
    .template-preview-name { font-size: 16px; font-weight: 700; color: #0f172a; margin: 0.55rem 0 0.3rem 0; }
    .template-preview-desc { font-size: 13px; color: #334155; line-height: 1.5; }
    .template-preview-hint { font-size: 12px; color: #64748b; margin-top: 0.55rem; }
    .template-preview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }
    .template-preview-mini { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; padding: 0.75rem; }
    .template-preview-mini.disabled { opacity: 0.45; }
    .template-preview-mini-name { font-size: 13px; font-weight: 700; color: #0f172a; margin-top: 0.3rem; }
    .template-preview-mini-meta { font-size: 11px; color: #64748b; margin-top: 0.25rem; }
    .settings-panel { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.25rem 1.35rem; margin: 1rem 0 1.35rem 0; }
    .settings-panel h4, .settings-panel .stMarkdown h4 { margin-top: 0; }
    .settings-panel [data-testid="stVerticalBlock"] { gap: 0.5rem; }
    .settings-hint-ok { color: var(--success); font-size: 12px; }
    .settings-hint-warn { color: var(--warning); font-size: 12px; }
    .provider-active-card { background: #eff6ff; border: 1px solid #93c5fd; border-left: 5px solid #1B2A4A; border-radius: 10px; padding: 1rem 1.15rem; margin: 0.5rem 0 1rem; }
    .provider-active-label { font-size: 11px; color: #1d4ed8; font-weight: 700; }
    .provider-active-name { font-size: 18px; color: #0f172a; font-weight: 700; margin: 0.12rem 0; }
    .provider-active-meta { font-size: 12px; color: #475569; }
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
        <p><strong>{BRAND_TITLE}</strong></p>
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
        "text_to_image_results": [],
        "text_to_image_error": "",
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


def render_demo_admin_panel():
    if not demo_mode_enabled():
        return
    st.markdown("#### 本地演示")
    st.caption("管理员 Demo 已开放，测试密钥不会访问外部 API。")
    if st.button("一键输入测试密钥", key="demo_seed_provider", width="stretch"):
        ensure_demo_provider(load_json(PROVIDERS_FILE, DEFAULT_PROVIDERS_DATA), set_current=True)
        st.session_state["demo_notice"] = "已启用本地演示管理员提供商。"
        st.rerun()
    if st.button("进入管理员入口", key="demo_open_admin", width="stretch"):
        set_nav_page("⚙️ 提供商设置")
        st.rerun()
    if notice := st.session_state.pop("demo_notice", ""):
        st.success(notice)


MODEL_CUSTOM_OPTION = "自定义…"
MODEL_UNSET_OPTION = "（留空，使用默认）"


def render_model_select_with_custom(
    label: str,
    catalog: list,
    current_value: str,
    key: str,
    allow_unset: bool = True,
    format_map: dict = None,
) -> str:
    """模型名下拉选择 + 自定义输入。

    catalog 内的已知模型用 selectbox 选择；选「自定义…」时展示文本框，
    允许中转提供商使用目录之外的模型名。返回最终模型名字符串（可为空）。
    """
    options = ([MODEL_UNSET_OPTION] if allow_unset else []) + list(catalog) + [
        MODEL_CUSTOM_OPTION
    ]
    cur = str(current_value or "").strip()
    if not cur and allow_unset:
        idx = 0
    elif cur in catalog:
        idx = options.index(cur)
    else:
        idx = len(options) - 1
    format_map = format_map or {}

    def _format_choice(value):
        if value in (MODEL_UNSET_OPTION, MODEL_CUSTOM_OPTION):
            return value
        return format_map.get(value, value)

    choice = st.selectbox(
        label,
        options,
        index=idx,
        key=f"{key}_sel",
        format_func=_format_choice,
    )
    if choice == MODEL_CUSTOM_OPTION:
        prefill = cur if cur and cur not in catalog else ""
        return st.text_input(
            f"{label} - 自定义模型名",
            value=prefill,
            key=f"{key}_custom",
            placeholder="例如 gpt-image-2",
        ).strip()
    if choice == MODEL_UNSET_OPTION:
        return ""
    return choice


MODEL_ROLE_KEYS = ("title", "vision", "image")
MODEL_ROLE_LABELS = {
    "title": "标题模型",
    "vision": "视觉模型",
    "image": "出图模型",
}
MODEL_IMAGE_TOKENS = (
    "image",
    "imagen",
    "dall-e",
    "flux",
    "banana",
    "stable-diffusion",
    "sdxl",
)
MODEL_VISION_TOKENS = (
    "vision",
    "-vl",
    "vl-",
    "4o",
    "4.1",
    "5.4",
    "gemini",
    "claude",
    "grok",
)


def _model_roles_for_entry(model_id: str, supported_methods=None) -> list:
    """Infer usable roles from upstream metadata, then use conservative name hints."""
    lowered = (model_id or "").lower()
    methods = {str(item).lower() for item in (supported_methods or [])}
    roles = set()
    if any("image" in method or "imagen" in method for method in methods):
        roles.add("image")
    if any(method in methods for method in ("generatecontent", "chatcompletion", "chat")):
        roles.update(("title", "vision"))
    is_image_model = any(token in lowered for token in MODEL_IMAGE_TOKENS)
    if is_image_model:
        roles.add("image")
    if any(token in lowered for token in MODEL_VISION_TOKENS):
        roles.add("vision")
    if is_image_model:
        roles.discard("title")
        roles.discard("vision")
    elif "vision" in roles:
        # Multimodal/text models can serve title generation as well as image understanding.
        roles.add("title")
    if not roles:
        roles.update(("title", "vision"))
    return [role for role in MODEL_ROLE_KEYS if role in roles]


def _normalize_model_catalog(entries: list) -> list:
    """Normalize Gemini/OpenAI-compatible model responses for JSON persistence."""
    normalized = []
    seen = set()
    for entry in entries or []:
        if isinstance(entry, str):
            raw_id, raw_name, methods = entry, entry, []
        elif isinstance(entry, dict):
            raw_id = entry.get("id") or entry.get("name") or entry.get("model")
            raw_name = entry.get("displayName") or entry.get("name") or raw_id
            methods = entry.get("supportedGenerationMethods") or entry.get(
                "supported_generation_methods"
            ) or entry.get("capabilities") or []
            if isinstance(methods, str):
                methods = [methods]
        else:
            continue
        model_id = str(raw_id or "").strip()
        if model_id.startswith("models/"):
            model_id = model_id.split("/", 1)[1]
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        roles = _model_roles_for_entry(model_id, methods)
        normalized.append(
            {
                "id": model_id,
                "name": str(raw_name or model_id).strip(),
                "roles": roles,
                "source": "upstream",
            }
        )
    return sorted(normalized, key=lambda item: (item.get("name", "").lower(), item["id"]))


def _provider_model_catalog(provider: dict) -> list:
    return _normalize_model_catalog((provider or {}).get("model_catalog") or [])


def _provider_model_choices(provider: dict, role: str) -> list:
    """Return fetched models first, then compatible built-ins for old providers."""
    fetched = _provider_model_catalog(provider)
    role_ids = [item["id"] for item in fetched if role in (item.get("roles") or [])]
    fetched_ids = role_ids or [item["id"] for item in fetched]
    builtins = list(MODELS.keys()) if role == "image" else list(TITLE_VISION_MODEL_ORDER)
    return list(dict.fromkeys(fetched_ids + builtins))


def _provider_model_labels(provider: dict, role: str) -> dict:
    labels = {}
    builtins = MODELS if role == "image" else TITLE_VISION_MODELS
    for model_id, info in builtins.items():
        labels[model_id] = info.get("name", model_id)
    labels.update({item["id"]: item.get("name", item["id"]) for item in _provider_model_catalog(provider)})
    return labels


def render_provider_model_select(
    label: str, provider: dict, role: str, current_value: str, key: str, allow_unset: bool = True
) -> str:
    choices = _provider_model_choices(provider, role)
    labels = _provider_model_labels(provider, role)
    return render_model_select_with_custom(
        label,
        choices,
        current_value,
        key,
        allow_unset=allow_unset,
        format_map=labels,
    )


def _model_endpoint(base_url: str, suffix: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return suffix.lstrip("/")
    if base.endswith("/models"):
        return base
    desired_version = ""
    if suffix.startswith("/v1beta"):
        desired_version = "/v1beta"
    elif suffix.startswith("/v1"):
        desired_version = "/v1"
    for version in ("/v1beta", "/v1"):
        if base.endswith(version):
            root = base[: -len(version)]
            return f"{root}{desired_version or version}/models"
    return f"{base}/{suffix.lstrip('/')}"


def _request_model_endpoint(endpoint: str, headers: dict):
    req = urllib.request.Request(endpoint, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {error.code}: {_extract_model_error(body)}") from error


def _extract_model_error(body: str) -> str:
    try:
        payload = json.loads(body or "{}")
    except json.JSONDecodeError:
        return (body or "请求失败")[:180]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or "请求失败")[:180]
    return str(payload.get("message") or "请求失败")[:180] if isinstance(payload, dict) else "请求失败"


def _model_entries_from_response(payload) -> list:
    if isinstance(payload, dict):
        entries = payload.get("data") or payload.get("models") or payload.get("items") or []
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []
    return entries if isinstance(entries, list) else []


def fetch_provider_models(provider: dict) -> list:
    """Fetch a provider's upstream model catalog without changing assignments."""
    provider = provider or {}
    api_key = resolve_provider_api_key(provider)
    if is_demo_api_key(api_key):
        demo_entries = [
            {"id": model_id, "displayName": info.get("name", model_id), "supportedGenerationMethods": ["generateContent"]}
            for model_id, info in MODELS.items()
        ] + [
            {"id": model_id, "displayName": info.get("name", model_id), "supportedGenerationMethods": ["generateContent"]}
            for model_id, info in TITLE_VISION_MODELS.items()
        ]
        return _normalize_model_catalog(demo_entries)
    if not api_key:
        raise RuntimeError("请先填写 API Key。")

    provider_type = (provider.get("provider_type") or "gemini").strip().lower()
    base_url = (provider.get("base_url") or "").strip()
    requests = []
    if provider_type == "openai":
        base = base_url or OPENAI_DEFAULT_BASE_URL
        requests = [
            (
                _model_endpoint(base, "/v1/models"),
                {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
        ]
    else:
        base = base_url or "https://generativelanguage.googleapis.com"
        requests = [
            (
                _model_endpoint(base, "/v1beta/models"),
                {"Accept": "application/json", "x-goog-api-key": api_key},
            )
        ]
        if provider_type == "relay":
            bearer_headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            requests.extend(
                [
                    (_model_endpoint(base, "/v1/models"), bearer_headers),
                    (_model_endpoint(base, "/models"), bearer_headers),
                ]
            )

    errors = []
    seen_endpoints = set()
    for endpoint, headers in requests:
        if endpoint in seen_endpoints:
            continue
        seen_endpoints.add(endpoint)
        try:
            payload = _request_model_endpoint(endpoint, headers)
            catalog = _normalize_model_catalog(_model_entries_from_response(payload))
            if catalog:
                return catalog
            errors.append(f"{endpoint}: 未返回模型")
        except Exception as error:
            errors.append(str(error))
    raise RuntimeError("；".join(errors)[:500] or "上游模型目录为空。")


def _collect_custom_model_names(provider: dict) -> list:
    """返回该提供商配置里不在内置目录中的模型名（自定义模型名）。"""
    customs = []
    image_model = str(provider.get("image_model", "") or "").strip()
    if image_model and image_model not in MODELS:
        customs.append(image_model)
    for field in ("title_model", "vision_model"):
        value = str(provider.get(field, "") or "").strip()
        if value and value not in TITLE_VISION_MODEL_ORDER:
            customs.append(value)
    return list(dict.fromkeys(customs))


def _provider_model_status(provider: dict) -> str:
    catalog = _provider_model_catalog(provider)
    if not catalog:
        return "尚未获取上游目录，当前使用内置候选。"
    updated = provider.get("model_catalog_updated_at") or "刚刚"
    return f"已获取 {len(catalog)} 个上游模型 · 最近更新 {updated}"


def show_provider_settings():
    st.markdown('<div class="page-title">⚙️ 提供商设置</div>', unsafe_allow_html=True)
    st.caption("管理 API 提供商、模型绑定与连接状态。任务页面会始终使用下方标记为“当前使用中”的提供商。")

    data = get_providers()
    providers = data.get("providers", [])
    current_id = data.get("current_id")
    current = next((p for p in providers if p.get("id") == current_id), None)
    if current:
        image_model = current.get("image_model") or "尚未选择"
        st.markdown(
            f'''<div class="provider-active-card">
<div class="provider-active-label">当前使用中</div>
<div class="provider-active-name">{esc(current.get("name", "未命名提供商"))}</div>
<div class="provider-active-meta">{esc(current.get("provider_type", "gemini").upper())} 协议 · 出图模型：{esc(image_model)} · {_provider_model_status(current)}</div>
</div>''',
            unsafe_allow_html=True,
        )
        provider_ids = [p.get("id", "") for p in providers if p.get("enabled", True)]
        if provider_ids:
            selected_id = st.selectbox(
                "当前提供商",
                provider_ids,
                index=provider_ids.index(current_id) if current_id in provider_ids else 0,
                format_func=lambda pid: next((p.get("name", "未命名提供商") for p in providers if p.get("id") == pid), pid),
                key="provider_current_picker",
                help="切换后，新的出图和标题任务会使用此提供商；已进入队列的任务不受影响。",
            )
            if selected_id != current_id:
                set_current_provider(selected_id)
                st.session_state["_provider_model_notice"] = "当前提供商已切换。"
                st.rerun()

    for notice_key in ("_provider_custom_model_notice", "_provider_model_notice"):
        notice = st.session_state.pop(notice_key, "")
        if notice:
            st.success(notice)

    if demo_mode_enabled():
        st.success("本地演示模式已开启。模型获取不会访问外部 API，可直接演练完整配置流程。")

    with st.expander("➕ 添加一个新提供商", expanded=not providers):
        st.caption("添加后会生成一张独立配置卡；你可以继续添加第二个、第三个提供商，再分别获取模型目录。")
        new_name = st.text_input("提供商名称", key="prov_new_name", placeholder="例如：我的 Gemini 中转")
        new_type = st.selectbox(
            "协议类型",
            ["gemini", "relay", "openai"],
            key="prov_new_type",
            format_func=lambda value: {
                "gemini": "Gemini 官方协议",
                "relay": "Gemini 协议中转站",
                "openai": "OpenAI 兼容协议",
            }.get(value, value),
        )
        new_key = st.text_input("API Key", type="password", key="prov_new_key")
        new_base = st.text_input(
            "Base URL" if new_type in ("relay", "openai") else "Base URL（可选）",
            key="prov_new_base",
            placeholder="例如 https://example.com/v1",
        )
        if st.button("添加提供商", type="primary", key="add_provider_btn"):
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
                    "title_model": "",
                    "vision_model": "",
                    "image_model": "",
                    "model_catalog": [],
                    "enabled": True,
                    "is_default": not providers,
                }
                try:
                    provider, _ = persist_provider_secret(provider, new_key)
                except RuntimeError as error:
                    st.error(sanitize_task_error(str(error)))
                else:
                    providers.append(provider)
                    if not data.get("current_id"):
                        data["current_id"] = new_id
                    data["providers"] = providers
                    save_providers(data)
                    st.session_state["_provider_model_notice"] = (
                        f"已添加「{provider['name']}」。现在点击该卡片里的“从上游获取模型”。"
                    )
                    storage_notice = provider_secret_storage_notice(provider)
                    if storage_notice:
                        st.session_state["_provider_model_notice"] += f" {storage_notice}"
                    st.rerun()

    if not providers:
        st.warning("还没有配置提供商。添加后可继续配置多个提供商。")
        return

    ordered_providers = sorted(
        providers,
        key=lambda provider: (provider.get("id") != data.get("current_id"), provider.get("name", "")),
    )
    st.markdown("#### 已保存的提供商")
    st.caption("当前提供商始终排在第一位。展开一张卡片后可编辑、同步模型目录、测试连接或保存更改。")
    for p in ordered_providers:
        provider_is_current = data.get("current_id") == p.get("id")
        state = "当前使用中" if provider_is_current else "备用"
        label = f"{'🟢 ' if provider_is_current else '⚪ '}{p.get('name', '提供商')} · {p.get('provider_type', 'gemini').upper()} · {state}"
        with st.expander(label, expanded=(data.get("current_id") == p.get("id"))):
            current_secret = resolve_provider_api_key(p)
            provider_active_tasks = provider_has_active_tasks(p.get("id"))
            st.caption(
                "此提供商正在被新任务使用。" if provider_is_current
                else "这是备用提供商；可先测试连接，再设为当前。"
            )
            p["name"] = st.text_input("名称", p.get("name", ""), key=f"prov_name_{p['id']}")
            p["provider_type"] = st.selectbox(
                "协议类型",
                ["gemini", "relay", "openai"],
                index=["gemini", "relay", "openai"].index(p.get("provider_type", "gemini"))
                if p.get("provider_type") in ["gemini", "relay", "openai"] else 0,
                key=f"prov_type_{p['id']}",
                format_func=lambda value: {
                    "gemini": "Gemini 官方协议",
                    "relay": "Gemini 协议中转站",
                    "openai": "OpenAI 兼容协议",
                }.get(value, value),
            )
            _key_input = st.text_input(
                "API Key", "", type="password", key=f"prov_key_{p['id']}", placeholder="留空表示不修改"
            )
            effective_secret = _key_input.strip() or current_secret
            if current_secret:
                st.caption(f"已保存 Key：{current_secret[:3]}***{current_secret[-4:]}")
            p["base_url"] = st.text_input("Base URL", p.get("base_url", ""), key=f"prov_base_{p['id']}")

            catalog = _provider_model_catalog(p)
            status_col, fetch_col = st.columns([3, 1])
            with status_col:
                st.markdown(f"**上游模型目录**  ·  {_provider_model_status(p)}")
                if p.get("model_catalog_error"):
                    st.warning(
                        "上次获取失败："
                        + sanitize_task_error(p["model_catalog_error"])
                    )
            with fetch_col:
                if st.button(
                    "🔄 从上游获取模型",
                    key=f"prov_fetch_models_{p['id']}",
                    disabled=not effective_secret,
                    width="stretch",
                ):
                    provider_for_fetch = provider_with_runtime_secret(
                        p, effective_secret
                    )
                    try:
                        with st.spinner("正在读取上游模型目录…"):
                            fetched_catalog = fetch_provider_models(provider_for_fetch)
                        p["model_catalog"] = fetched_catalog
                        p["model_catalog_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        p["model_catalog_error"] = ""
                        if _key_input.strip():
                            prepared, provider_errors, _ = prepare_provider_for_save(
                                p, _key_input.strip()
                            )
                            if provider_errors:
                                raise ValueError("；".join(provider_errors))
                            p.update(prepared)
                        data["providers"] = providers
                        save_providers(data)
                        st.session_state["_provider_model_notice"] = (
                            f"「{p.get('name', '提供商')}」已加载 {len(fetched_catalog)} 个模型。"
                        )
                        st.rerun()
                    except Exception as error:
                        p["model_catalog_error"] = sanitize_task_error(
                            str(error), secrets=(effective_secret,)
                        )
                        data["providers"] = providers
                        save_providers(data)
                        st.error(f"模型获取失败：{p['model_catalog_error']}")

            st.markdown("##### 模型绑定")
            st.caption("绑定只对当前提供商生效；任务页会默认使用这里的选择，也可以在任务中临时切换。")
            p["title_model"] = render_provider_model_select(
                "标题模型", p, "title", p.get("title_model", ""), key=f"prov_title_{p['id']}"
            )
            p["vision_model"] = render_provider_model_select(
                "视觉模型", p, "vision", p.get("vision_model", ""), key=f"prov_vision_{p['id']}"
            )
            p["image_model"] = render_provider_model_select(
                "出图模型", p, "image", p.get("image_model", ""), key=f"prov_image_{p['id']}"
            )
            p["enabled"] = st.checkbox("启用此提供商", p.get("enabled", True), key=f"prov_enabled_{p['id']}")

            if provider_active_tasks:
                st.warning("当前有进行中任务正在使用该提供商，暂不允许删除。")
            if provider_is_current:
                st.caption("当前默认提供商")

            st.markdown("##### 操作")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✓ 当前使用中" if provider_is_current else "设为当前", key=f"prov_set_{p['id']}", disabled=provider_is_current, type="primary" if not provider_is_current else "secondary", width="stretch"):
                    set_current_provider(p["id"])
                    st.session_state["_provider_model_notice"] = f"已切换当前提供商：{p.get('name', '提供商')}。"
                    st.rerun()
            with c2:
                if st.button("测试 API 连接", key=f"prov_test_{p['id']}", disabled=not effective_secret, width="stretch"):
                    provider_for_test = provider_with_runtime_secret(
                        p, effective_secret
                    )
                    provider_errors = validate_provider_config(
                        p.get("name", ""), p.get("provider_type", "gemini"), effective_secret, p.get("base_url", "")
                    )
                    if provider_errors:
                        st.error("；".join(provider_errors))
                    else:
                        try:
                            reply = create_ai_client(provider_for_test).test_connection()
                            st.success(f"✅ 连接成功：{(reply or '').strip()[:60]}")
                        except Exception as error:
                            st.error(
                                sanitize_task_error(
                                    str(error), secrets=(effective_secret,)
                                )
                            )
            with c3:
                if st.button("保存更改", key=f"prov_save_{p['id']}", width="stretch"):
                    try:
                        prepared, provider_errors, _ = prepare_provider_for_save(
                            p, _key_input
                        )
                        if provider_errors:
                            for error in provider_errors:
                                st.error(error)
                        else:
                            p.update(prepared)
                            data["providers"] = providers
                            save_providers(data)
                            st.success(f"✅ 已保存「{p.get('name', '提供商')}」")
                    except RuntimeError as error:
                        st.error(sanitize_task_error(str(error)))
            with st.expander("危险操作", expanded=False):
                delete_confirm_key = f"confirm_delete_provider_{p['id']}"
                st.caption("删除会移除此提供商配置；当前提供商会自动切换到其余可用项。")
                if st.button("删除此提供商", key=f"prov_del_{p['id']}", disabled=provider_active_tasks, width="stretch"):
                    activate_confirmation(delete_confirm_key)
                    st.rerun()
                replacement = find_replacement_provider(p.get("id"))
                delete_message = "删除后会移除该提供商配置。"
                if provider_is_current:
                    delete_message += (
                        f" 当前默认将切换为 {replacement.get('name', '其他提供商')}。"
                        if replacement else " 删除后当前默认提供商将被清空。"
                    )
                if render_confirmation_bar(delete_confirm_key, delete_message, confirm_label="确认删除提供商"):
                    delete_keychain_secret(p.get("keychain_account"))
                    providers.remove(p)
                    if provider_is_current:
                        data["current_id"] = replacement.get("id", "") if replacement else ""
                    data["providers"] = providers
                    save_providers(data)
                    st.success("✅ 已删除提供商")
                    st.rerun()

    st.caption("模型目录获取会立即保存；名称、协议、模型绑定和启用状态可在卡片内保存。")


def show_settings_center():
    st.markdown('<div class="page-title">🛠️ 系统设置</div>', unsafe_allow_html=True)
    st.markdown(
        "系统设置只处理运行行为、内容默认、诊断与合规；提供商、模型目录和连接测试统一放在「提供商设置」。"
    )

    tabs = st.tabs(["⚙️ 运行与存储", "🌐 内容默认", "🩺 诊断", "🛡️ 合规词", "🧠 提示词"])

    with tabs[0]:
        render_settings_runtime_tab()

    with tabs[1]:
        render_settings_defaults_tab()

    with tabs[2]:
        render_settings_diagnostics_tab()

    with tabs[3]:
        st.markdown("### 🛡️ 个人合规词管理")
        st.caption("这里的合规词用于图片文案、图需和图片翻译；商品标题使用固定的 TEMU 三语合规规则。")
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

    with tabs[4]:
        render_prompt_management()


# ==================== 标题生成选项组件 ====================
def render_title_gen_option(prefix: str, provider: dict = None):
    st.markdown("---")
    st.markdown("### 🏷️ 智能标题生成 (可选)")

    enable_title = st.checkbox(
        "📝 同时生成商品标题",
        key=f"{prefix}_enable_title",
        help="勾选后将在出图完成时一并生成 TEMU 三语标题（中文 / Español / Français）",
    )

    if enable_title:
        st.markdown('<div class="title-box">', unsafe_allow_html=True)

        target_language = DEFAULT_TARGET_LANGUAGE  # 三语标题固定输出 zh/es/fr
        st.caption("输出固定为 TEMU 三语标题：🇨🇳 中文 · 🇪🇸 Español · 🇫🇷 Français（西/法附中文回译）")
        st.caption("标题策略：内置 TEMU 三语生成与合规自查")

        title_info = st.text_area(
            f"商品信息描述 (最多{MAX_TITLE_INFO_CHARS}字)",
            height=100,
            max_chars=MAX_TITLE_INFO_CHARS,
            key=f"{prefix}_title_info",
            placeholder="输入商品的详细信息，如：名称、材质、规格、特点、用途等...",
        )

        char_count = len(title_info) if title_info else 0
        st.caption(f"已输入 {char_count}/{MAX_TITLE_INFO_CHARS} 字符")

        provider = provider or {}
        provider_default_model = provider.get("title_model") or provider.get(
            "vision_model", ""
        )
        default_title_vision_model = provider_default_model or resolve_default_title_vision_model(
            provider_default_model
        )
        with st.expander("⚙️ 高级：标题生成模型（默认沿用提供商配置，一般无需修改）"):
            title_vision_model = render_provider_model_select(
                "标题生成模型",
                provider,
                "vision",
                default_title_vision_model,
                key=f"{prefix}_title_vision_model",
                allow_unset=False,
            )
            st.caption("当前列表优先显示该提供商上游目录；未获取目录时显示内置候选。")

        st.markdown("</div>", unsafe_allow_html=True)

        return (
            enable_title,
            title_info,
            "default",
            target_language,
            title_vision_model,
        )

    provider = provider or {}
    fallback_model = resolve_default_title_vision_model(
        provider.get("title_model") or provider.get("vision_model", "")
    )
    return (
        False,
        "",
        "default",
        st.session_state.get(f"{prefix}_title_language", DEFAULT_TARGET_LANGUAGE),
        fallback_model,
    )


def display_generated_titles(
    titles: list, prefix: str = "", target_language: str = "zh"
):
    """TEMU 三语标题展示：中文 / Español(+回译) / Français(+回译)。

    target_language 参数保留以兼容旧调用（不再影响输出布局）；
    同时兼容旧历史记录中的纯字符串标题。"""
    if not titles:
        return

    entries = normalize_title_entries(titles)
    if not entries:
        return

    st.markdown("### 🏷️ 生成的商品标题 (TEMU 三语：中文 / Español / Français)")

    issue_entries = [e for e in entries if e.get("lang") == "issue"]
    title_entries = [e for e in entries if e.get("lang") != "issue"]

    for entry in title_entries:
        lang = entry.get("lang", "")
        label = TRI_TITLE_LABELS.get(lang, lang or "标题")
        flag = TRI_TITLE_FLAGS.get(lang, "🏷️")
        chars = entry.get("chars", len(entry.get("title", "")))
        range_min, range_max = get_title_char_range(lang)
        in_range = range_min <= chars <= range_max
        char_status = "✅" if in_range else "⚠️"
        back = entry.get("back_translation_zh", "")
        back_html = (
            f"""<div style="background:#fef3c7;padding:0.5rem;border-radius:6px;margin-top:0.5rem">
                    <span style="font-size:11px;color:#92400e">🇨🇳 中文回译</span><br>
                    <span style="font-size:13px">{esc(back)}</span>
                </div>"""
            if back
            else ""
        )
        st.markdown(
            f"""
        <div class="title-bilingual">
            <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem">
                <span style="color:#6366f1;font-weight:600">{flag} {esc(label)}</span>
                <span style="font-size:11px;color:#64748b">{char_status} {chars}字符</span>
            </div>
            <div style="background:#e0e7ff;padding:0.5rem;border-radius:6px">
                <span style="font-size:14px">{esc(entry.get("title", ""))}</span>
            </div>
            {back_html}
        </div>
        """,
            unsafe_allow_html=True,
        )
        if not in_range:
            st.caption(
                f"⚠️ {label} 标题 {chars} 字符，超出/不足 TEMU 建议区间 "
                f"({range_min}-{range_max} 字符)"
            )

    for entry in issue_entries:
        st.warning(f"⚠️ {entry.get('title', '')}")

    # 复制区域
    copy_text = format_titles_text(entries)
    st.text_area(
        "📋 复制全部标题",
        copy_text,
        height=160,
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
            "✅ 一键全选", key=f"{prefix}_select_all", width="stretch"
        ):
            for tk in enabled_templates:
                st.session_state[sel_key(tk)] = True
            st.rerun()

    with col2:
        if st.button(
            "🔄 清空选择", key=f"{prefix}_clear_all", width="stretch"
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


def render_settings_runtime_tab():
    s = get_settings()
    st.markdown("### ⚙️ 运行与存储")
    st.caption("这里控制任务队列、并发、代理和文件清理；提供商凭据、模型获取和连接测试请在「提供商设置」完成。")

    max_active_tasks = st.number_input(
        "同时执行的任务数",
        min_value=1,
        max_value=16,
        step=1,
        value=get_task_limits(s)[0],
        key="settings_max_active_tasks",
        help="任务越多越快，但也会增加上游限流、网络和本机资源压力。",
    )
    max_task_queue = st.number_input(
        "任务中心最多保留",
        min_value=1,
        max_value=100,
        step=1,
        value=get_task_limits(s)[1],
        key="settings_max_task_queue",
        help="达到上限时会优先复用已结束任务的位置；不会删除正在运行的任务。",
    )
    c1, c2 = st.columns(2)
    with c1:
        trash_retention_days = st.number_input(
            "回收站保留天数",
            min_value=0,
            max_value=3650,
            step=1,
            value=int(s.get("trash_retention_days", 15)),
            key="settings_trash_retention_days",
            help="0 表示不自动清理。",
        )
        file_retention_days = st.number_input(
            "文件保留天数",
            min_value=0,
            max_value=3650,
            step=1,
            value=int(s.get("file_retention_days", 7)),
            key="settings_file_retention_days",
            help="0 表示不自动清理临时文件。",
        )
    with c2:
        proxy_mode = st.selectbox(
            "代理模式",
            ["system", "manual", "none"],
            index=["system", "manual", "none"].index(s.get("proxy_mode", "system"))
            if s.get("proxy_mode", "system") in ["system", "manual", "none"] else 0,
            format_func=lambda x: {"system": "跟随系统", "manual": "手动代理", "none": "不使用代理"}.get(x, x),
            key="settings_proxy_mode",
        )
        proxy_url = st.text_input(
            "手动代理地址",
            value=s.get("proxy_url", "http://127.0.0.1:10808"),
            key="settings_proxy_url",
            help="例如 http://127.0.0.1:10808；仅在手动代理时使用。",
        )

    current_output_dir = s.get("project_output_dir", _default_project_output_dir())
    if runtime_supports_output_dir_editing():
        project_output_dir = st.text_input(
            "项目保存目录",
            value=current_output_dir,
            key="settings_project_output_dir",
            help="标题、图片、ZIP 和错误日志都会按项目文件夹保存。",
        )
    else:
        project_output_dir = current_output_dir
        st.text_input("服务器项目目录", value=current_output_dir, disabled=True, key="settings_project_output_dir_server")
        st.caption("当前运行模式不会直接操作访问者电脑上的文件夹，结果会进入服务器项目中心。")

    st.markdown("---")
    st.caption("保存后，新的任务会使用并发和队列上限；正在运行的任务不会被中断。")
    if st.button("💾 应用运行设置", type="primary", key="save_runtime_settings"):
        s["max_active_tasks"] = int(max_active_tasks)
        s["max_task_queue"] = int(max_task_queue)
        s["trash_retention_days"] = int(trash_retention_days)
        s["file_retention_days"] = int(file_retention_days)
        s["project_output_dir"] = project_output_dir.strip()
        s["proxy_mode"] = proxy_mode
        s["proxy_url"] = proxy_url.strip()
        save_settings(s)
        apply_proxy_settings(s)
        st.success("✅ 运行设置已应用")


def render_settings_defaults_tab():
    s = get_settings()
    st.markdown("### 🌐 内容默认")
    st.caption("模型不再在这里维护；请到每个提供商卡片获取上游目录并绑定模型。")
    c1, c2 = st.columns(2)
    with c1:
        title_language_options = [item["code"] for item in TARGET_LANGUAGES]
        default_title_language = st.selectbox(
            "默认标题语言",
            title_language_options,
            index=title_language_options.index(s.get("default_title_language", DEFAULT_TARGET_LANGUAGE))
            if s.get("default_title_language", DEFAULT_TARGET_LANGUAGE) in title_language_options else 0,
            format_func=format_target_language_option,
            key="settings_default_title_language",
            help="标题功能当前固定输出 TEMU 三语；此项保留用于兼容历史设置。",
        )
        default_image_language = st.selectbox(
            "默认图片文案语言",
            title_language_options,
            index=title_language_options.index(s.get("default_image_language", DEFAULT_TARGET_LANGUAGE))
            if s.get("default_image_language", DEFAULT_TARGET_LANGUAGE) in title_language_options else 0,
            format_func=format_target_language_option,
            key="settings_default_image_language",
        )
        enabled_modes = [k for k, v in get_compliance().get("presets", {}).items() if v.get("enabled", True)] or ["strict"]
        compliance_mode = st.selectbox(
            "默认合规模式",
            enabled_modes,
            index=enabled_modes.index(s.get("compliance_mode", "strict")) if s.get("compliance_mode", "strict") in enabled_modes else 0,
            format_func=lambda x: get_compliance().get("presets", {}).get(x, {}).get("name", x),
            key="settings_compliance_mode",
        )
    with c2:
        default_aspect = st.selectbox(
            "默认宽高比",
            ASPECT_RATIOS,
            index=ASPECT_RATIOS.index(s.get("default_aspect", "1:1")) if s.get("default_aspect", "1:1") in ASPECT_RATIOS else 0,
            key="settings_default_aspect",
        )
        default_resolution = st.selectbox(
            "默认分辨率",
            ["1K", "2K", "4K"],
            index=["1K", "2K", "4K"].index(s.get("default_resolution", "1K")) if s.get("default_resolution", "1K") in ["1K", "2K", "4K"] else 0,
            help="具体可选项仍取决于当前提供商和出图模型。",
            key="settings_default_resolution",
        )
        default_thinking_level = st.selectbox(
            "默认推理深度",
            ["low", "high"],
            index=["low", "high"].index(s.get("default_thinking_level", "high")) if s.get("default_thinking_level", "high") in ["low", "high"] else 0,
            format_func=lambda x: THINKING_LEVEL_DESC.get(x, x),
            key="settings_default_thinking_level",
            help="仅对支持推理深度的模型生效。",
        )

    st.markdown("---")
    if st.button("💾 保存内容默认", type="primary", key="save_content_defaults"):
        s["default_title_language"] = default_title_language
        s["default_image_language"] = default_image_language
        s["compliance_mode"] = compliance_mode
        s["default_resolution"] = default_resolution
        s["default_aspect"] = default_aspect
        s["default_thinking_level"] = default_thinking_level
        save_settings(s)
        st.session_state.user_compliance_mode = compliance_mode
        st.success("✅ 内容默认已保存")


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
    st.markdown("统一管理图片生成与翻译模板。标题统一使用内置 TEMU 三语策略。")

    diagnostics = collect_template_library_diagnostics()
    d1, d2 = st.columns(2)
    d1.metric("图片模板", diagnostics["image_template_count"])
    d2.metric("启用翻译模板", diagnostics["enabled_translation_count"])

    if diagnostics["issues"]:
        st.warning("模板库健康检查发现潜在问题。建议修正后再交给业务页面使用。")
        for issue in diagnostics["issues"][:8]:
            st.caption(f"• {issue}")
    else:
        st.success("模板库健康检查通过。当前模板结构与关键占位符完整。")

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


# ==================== 出图设置统一面板 ====================
def render_output_settings_panel(prefix: str, provider: dict, s: dict) -> dict:
    """把模型、合规模式、宽高比、分辨率、推理深度这些"这次怎么出图"的参数
    统一渲染在一个卡片区域里，smart 页和 combo 页共用，避免设置分散在侧边栏/多个 Tab。"""
    provider = provider or {}
    st.markdown('<div class="settings-panel">', unsafe_allow_html=True)
    st.markdown("#### 🎛️ 这次出图设置")

    model_keys = _provider_model_choices(provider, "image")
    provider_model = (provider.get("image_model") or "").strip()
    fallback_default = provider_model or s.get("default_model", "nano-banana")
    if fallback_default not in model_keys:
        model_keys.append(fallback_default)
        st.warning("当前提供商配置了一个不在已获取目录中的模型，已保留该自定义值。")

    model_select_key = f"{prefix}_output_model"
    if model_select_key not in st.session_state or st.session_state[model_select_key] not in model_keys:
        st.session_state[model_select_key] = fallback_default

    c1, c2 = st.columns([2, 1])
    with c1:
        model_labels = _provider_model_labels(provider, "image")
        model = st.selectbox(
            "🤖 出图模型",
            model_keys,
            format_func=lambda x: model_labels.get(x, x),
            key=model_select_key,
            help="默认取当前提供商配置的模型，也可以在这里临时切换；列表优先来自上游模型目录。",
        )
    with c2:
        comp = get_compliance()
        mode_options = {
            k: v["name"] for k, v in comp["presets"].items() if v.get("enabled", True)
        }
        mode_keys = list(mode_options.keys()) or ["strict"]
        current_mode = st.session_state.get("user_compliance_mode", s.get("compliance_mode", "strict"))
        if current_mode not in mode_keys:
            current_mode = mode_keys[0]
        compliance_mode = st.selectbox(
            "🛡️ 合规模式",
            mode_keys,
            index=mode_keys.index(current_mode),
            format_func=lambda x: mode_options.get(x, x),
            key=f"{prefix}_output_compliance_mode",
            help="控制文案/图需的合规检测严格程度。",
        )
        st.session_state.user_compliance_mode = compliance_mode

    aspect, size, thinking_level = render_gemini3_settings(prefix, model)

    st.markdown("</div>", unsafe_allow_html=True)

    return {
        "model": model,
        "aspect": aspect,
        "resolution": size,
        "thinking_level": thinking_level,
        "compliance_mode": compliance_mode,
    }


# ==================== Gemini 3 高级设置 ====================
def render_gemini3_settings(prefix: str, model_key: str):
    s = get_settings()
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

    # 固定使用3列布局，避免不同模型能力导致页面跳变
    c1, c2, c3 = st.columns(3)

    with c1:
        default_aspect = s.get("default_aspect", "1:1")
        aspect_index = (
            ASPECT_RATIOS.index(default_aspect) if default_aspect in ASPECT_RATIOS else 0
        )
        aspect = st.selectbox(
            "📐 宽高比", ASPECT_RATIOS, index=aspect_index, key=f"{prefix}_aspect"
        )

    with c2:
        available_res = model_info.get("resolutions", ["1K"])
        default_resolution = s.get("default_resolution", "1K")
        res_index = (
            available_res.index(default_resolution)
            if default_resolution in available_res
            else 0
        )
        size = st.selectbox(
            "🖼️ 分辨率", available_res, index=res_index, key=f"{prefix}_size"
        )

    thinking_level = "high"  # 默认值

    with c3:
        if supports_thinking:
            thinking_levels = model_info.get("thinking_levels", ["low", "high"])
            default_thinking = s.get(
                "default_thinking_level", model_info.get("default_thinking", "high")
            )
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
                help="仅部分模型（如 Nano Banana Pro）支持此功能",
            )
        else:
            st.markdown("🧠 推理深度")
            st.caption(f"💡 {model_info.get('name', model_key)} 不支持推理深度调节")

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

        # 固定网格列数：单张结果也保持缩略图尺寸，避免大图占满页面。
        cols = st.columns(3)
        for i, item in enumerate(results):
            with cols[i % len(cols)]:
                img = item.get("image")
                label = item.get("label", f"图片{i + 1}")
                filename = item.get("filename", f"image_{i + 1}.png")

                if img:
                    st.image(img, caption=label, width="stretch")
                    st.caption(f"📁 {filename}")

        # 下载按钮
        st.markdown("---")
        result_sig = hashlib.md5(
            repr(
                [
                    (item.get("filename"), item.get("label"))
                    for item in results
                ]
                + list(titles or [])
                + [target_language, len(results)]
            ).encode("utf-8")
        ).hexdigest()
        zip_cache = st.session_state.get(f"{prefix}_zip_cache")
        if zip_cache and zip_cache[0] == result_sig:
            zip_bytes = zip_cache[1]
        else:
            zip_bytes = create_zip_from_results(results, titles, target_language)
            st.session_state[f"{prefix}_zip_cache"] = (result_sig, zip_bytes)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ 下载全部 (ZIP)",
                data=zip_bytes,
                file_name=f"images_{date.today()}.zip",
                mime="application/zip",
                type="primary",
                width="stretch",
            )

        with col2:
            # 持久化存储：同一批结果只上传一次
            persist_cache = st.session_state.get(f"{prefix}_persisted_sig")
            if persist_cache and persist_cache[0] == result_sig:
                stype, retention, url, err = persist_cache[1]
            else:
                stype, retention, url, err = maybe_persist_and_upload(
                    zip_bytes, f"images_{date.today()}.zip"
                )
                st.session_state[f"{prefix}_persisted_sig"] = (
                    result_sig,
                    (stype, retention, url, err),
                )
            if url:
                st.link_button("🌐 云端下载链接", url, width="stretch")

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


def can_submit_smart_generation(images, workflow_mode: str, total_count: int) -> bool:
    return bool(images) and (workflow_mode == "translate" or total_count > 0)


def build_smart_task_summary(
    workflow_mode: str, product_name: str, total_count: int, image_count: int
) -> str:
    name = str(product_name or "").strip()
    if workflow_mode == "translate":
        return f"组图翻译任务 · {name or '未命名项目'} · {image_count}张"
    return f"快速出图任务 · {name or 'AI识图'} · {total_count}张"


def append_smart_generation_instruction(
    base_prompt: str, user_instruction: str
) -> str:
    instruction = str(user_instruction or "").strip()
    if not instruction:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "USER CREATIVE DIRECTION:\n"
        f"{instruction}\n\n"
        "Keep the product identity faithful to the reference image; do not alter "
        "its shape, color, material, branding, or logo unless the reference "
        "image itself supports it."
    )


def append_smart_generation_compliance_rules(
    base_prompt: str, compliance_mode: str
) -> str:
    rules = str(get_compliance_prompt(compliance_mode) or "").strip()
    if not rules:
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "MANDATORY COMPLIANCE RULES:\n"
        f"{rules}\n"
        "These rules override any user creative direction and must be followed."
    )


def validate_smart_generation_instruction(
    user_instruction: str, compliance_mode: str, user_id=None
) -> tuple[str, str]:
    instruction = str(user_instruction or "").strip()
    if not instruction:
        return "", ""
    allowed, cleaned_instruction, note = check_compliance(
        instruction, compliance_mode, user_id=user_id
    )
    if not allowed:
        return "", f"补充提示词未通过合规检测：{note or '请调整后重试。'}"
    return str(cleaned_instruction or instruction).strip(), ""


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


SUITE_TASK_VERSION = 1


def _persisted_asset_path_map(persisted_assets) -> dict:
    if isinstance(persisted_assets, Mapping):
        entries = persisted_assets.items()
    elif isinstance(persisted_assets, (list, tuple)):
        entries = []
        for asset in persisted_assets:
            if not isinstance(asset, Mapping):
                raise ValueError("persisted_assets must contain id/path mappings")
            entries.append((asset.get("id"), asset.get("path")))
    else:
        raise ValueError("persisted_assets must be an id-to-path mapping or asset list")

    paths_by_id = {}
    for raw_asset_id, raw_path in entries:
        asset_id = str(raw_asset_id or "").strip()
        path = str(raw_path or "").strip()
        if not asset_id or not path:
            raise ValueError("persisted_assets must contain non-empty id/path values")
        if asset_id in paths_by_id:
            raise ValueError(f"duplicate persisted asset id: {asset_id}")
        paths_by_id[asset_id] = path
    return paths_by_id


def build_suite_task_requests(plan, persisted_assets) -> list[dict]:
    """Freeze approved plan items with their selected durable image paths."""
    if not isinstance(plan, Mapping) or not isinstance(plan.get("plan_items"), list):
        raise ValueError("plan must contain a plan_items list")
    paths_by_id = _persisted_asset_path_map(persisted_assets)
    return [
        _build_suite_task_request(item, paths_by_id, index)
        for index, item in enumerate(plan["plan_items"], start=1)
    ]


def _build_suite_task_request(item, paths_by_id: Mapping, index: int) -> dict:
    if not isinstance(item, Mapping):
        raise ValueError(f"plan item {index} must be a mapping")
    item_id = item.get("id")
    type_key = item.get("type_key")
    title = item.get("title")
    final_prompt = item.get("final_prompt")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (item_id, type_key, title, final_prompt)
    ):
        raise ValueError(
            f"plan item {index} must contain id, type_key, title, and final_prompt"
        )
    reference_ids = item.get("reference_asset_ids")
    if (
        not isinstance(reference_ids, list)
        or not 1 <= len(reference_ids) <= 3
        or any(
            not isinstance(asset_id, str) or not asset_id.strip()
            for asset_id in reference_ids
        )
        or len(set(reference_ids)) != len(reference_ids)
    ):
        raise ValueError(
            f"plan item {item_id} must contain one to three unique reference_asset_ids"
        )
    missing_ids = [asset_id for asset_id in reference_ids if asset_id not in paths_by_id]
    if missing_ids:
        raise ValueError(
            f"plan item {item_id} references missing persisted asset: {missing_ids[0]}"
        )
    return {
        "id": item_id,
        "type_key": type_key,
        "type_name": title,
        "title": title,
        "final_prompt": final_prompt,
        "reference_asset_ids": list(reference_ids),
        "image_paths": [paths_by_id[asset_id] for asset_id in reference_ids],
    }


def _execute_title_task(execution: TaskExecution):
    task = execution.task
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    client = create_ai_client(
        provider,
        title_model=payload.get("title_model"),
        vision_model=payload.get("vision_model"),
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
        "titles": merge_titles_and_issues(result),
        "errors": [],
        "files": [],
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def _execute_smart_task(execution: TaskExecution):
    task = execution.task
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    images = load_image_paths(payload.get("image_paths", []))
    if not images:
        raise Exception("任务图片已丢失，请重新上传")
    image_language = payload.get("image_language", DEFAULT_TARGET_LANGUAGE)
    results = []
    errors = []
    retry_items = payload.get("retry_items", []) or []
    user_instruction = ""
    if not retry_items:
        user_instruction, instruction_error = validate_smart_generation_instruction(
            payload.get("user_instruction", ""),
            str(payload.get("compliance_mode") or "strict"),
            user_id=str(payload.get("compliance_user_id") or ""),
        )
        if instruction_error:
            raise ValueError(instruction_error)
    analysis_client = None
    if retry_items:
        item_jobs = [
            {
                "type_name": item.get("type_name", "图片"),
                "index": item.get("index", index + 1),
                "prompt": item.get("prompt", ""),
            }
            for index, item in enumerate(retry_items)
            if item.get("prompt")
        ]
    else:
        templates = get_template_group("smart_types")
        analysis_client = create_ai_client(
            provider,
            model=payload.get("model", provider.get("image_model", "")),
            title_model=payload.get("title_model"),
            vision_model=payload.get("vision_model"),
        )
        anchor = analysis_client.analyze_product(
            images, payload.get("name", ""), payload.get("material", "")
        )
        selected_types = payload.get("selected_types", {})
        requirements = build_smart_requirements(selected_types, templates)
        requirements = analysis_client.generate_en_copy(
            anchor, requirements, image_language
        )
        req_map = {
            (req.get("type_key"), req.get("index")): req for req in requirements
        }
        item_jobs = []
        for tk, cnt in selected_types.items():
            info = templates[tk]
            for idx in range(cnt):
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
                prompt = analysis_client.compose_image_prompt(
                    anchor, req, payload.get("aspect", "1:1"), image_language
                )
                prompt = append_smart_generation_instruction(
                    prompt, user_instruction
                )
                if user_instruction:
                    prompt = append_smart_generation_compliance_rules(
                        prompt, payload.get("compliance_mode", "strict")
                    )
                item_jobs.append(
                    {
                        "type_name": info["name"],
                        "index": idx + 1,
                        "prompt": prompt,
                    }
                )
    total = len(item_jobs)
    if not total:
        raise Exception("没有可执行的图片生成项")

    # 每项只使用主体参考图，避免把全部上传图重复发送到每个上游请求。
    refs = images[:1]
    completed = 0
    item_results = []

    def generate_item(item):
        execution.raise_if_stopped()
        started_at = time.monotonic()
        try:
            client = create_ai_client(
                provider,
                model=payload.get("model", provider.get("image_model", "")),
            )
            image = client.generate_image(
                refs,
                item["prompt"],
                payload.get("aspect", "1:1"),
                payload.get("size", "1K"),
                payload.get("thinking_level", "high"),
                image_language,
            )
            if not image:
                raise RuntimeError(
                    client.get_last_error() or f"{item['type_name']} 生成失败"
                )
            filename = f"{task['id']}_{item['index']:02d}_{item['type_name']}.png"
            return (
                item,
                persist_image_for_task(image, filename),
                round(time.monotonic() - started_at, 1),
                None,
            )
        except Exception as error:
            return (
                item,
                "",
                round(time.monotonic() - started_at, 1),
                error,
            )

    with ThreadPoolExecutor(max_workers=min(2, max(1, total))) as executor:
        futures = {executor.submit(generate_item, item): item for item in item_jobs}
        for future in as_completed(futures):
            item = futures[future]
            completed += 1
            finished_item, file_path, elapsed_seconds, item_error = future.result()
            if item_error is None:
                results.append(file_path)
                item_results.append(
                    {
                        **finished_item,
                        "status": "done",
                        "file_path": file_path,
                        "elapsed_seconds": elapsed_seconds,
                    }
                )
            else:
                error_meta = classify_provider_image_task_error(
                    str(item_error),
                    provider,
                )
                errors.append(error_meta["error"])
                item_results.append(
                    {
                        **item,
                        "status": "error",
                        "elapsed_seconds": elapsed_seconds,
                        **error_meta,
                    }
                )
            execution.checkpoint(
                progress={
                    "done": completed,
                    "total": total,
                    "success": len(results),
                    "failed": len(errors),
                },
                item_results=item_results,
                result_files=results,
                errors=errors,
            )
    titles = []
    if analysis_client and payload.get("enable_title") and payload.get("title_info"):
        title_result = analysis_client.generate_titles(
            payload.get("title_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
        if title_result.get("success"):
            titles = merge_titles_and_issues(title_result)
        else:
            errors.append(format_title_error(title_result))
    return {
        "titles": titles,
        "errors": errors,
        "files": results,
        "item_results": item_results,
        "partial": bool(errors),
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def _execute_translate_task(execution: TaskExecution):
    task = execution.task
    payload = task.get("payload", {})
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    images = load_image_paths(payload.get("image_paths", []))
    if not images:
        raise Exception("任务图片已丢失，请重新上传")
    client = create_ai_client(
        provider, model=payload.get("model", provider.get("image_model", ""))
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
    item_results = []
    total = len(images)
    for idx, image in enumerate(images):
        execution.raise_if_stopped()
        error_meta = None
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
            error_meta = classify_provider_image_task_error(str(e), provider)
            safe_exception = RuntimeError(error_meta["error"]).with_traceback(
                e.__traceback__
            )
            logger.error(
                "task image translation failed (task_id=%s)",
                task.get("id"),
                exc_info=(RuntimeError, safe_exception, e.__traceback__),
            )
            client.last_error = error_meta["error"]
            translated = None
        if translated:
            filename = f"{task['id']}_{str(idx + 1).zfill(2)}_translated.png"
            file_path = persist_image_for_task(translated, filename)
            results.append(file_path)
            item_results.append(
                {
                    "index": idx + 1,
                    "type_name": "图片翻译",
                    "status": "done",
                    "file_path": file_path,
                }
            )
        else:
            if error_meta is None:
                error_meta = classify_provider_image_task_error(
                    client.get_last_error() or f"第{idx + 1}张翻译失败",
                    provider,
                )
            errors.append(error_meta["error"])
            item_results.append(
                {
                    "index": idx + 1,
                    "type_name": "图片翻译",
                    "status": "error",
                    **error_meta,
                }
            )
        execution.checkpoint(
            progress={"done": idx + 1, "total": total},
            result_files=results,
            errors=errors,
            item_results=item_results,
        )
    if not results and errors:
        raise Exception(errors[0])
    return {
        "titles": [],
        "errors": errors,
        "files": results,
        "item_results": item_results,
        "partial": bool(errors),
        "target_language": image_language,
    }


def _execute_combo_task(execution: TaskExecution):
    task = execution.task
    payload = task.get("payload", {})
    is_suite_task = "suite_version" in payload
    provider = (
        get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    refs = None
    if not is_suite_task:
        refs = load_image_paths(payload.get("image_paths", []))
        if not refs:
            raise Exception("任务参考图已丢失，请重新上传")
    reqs = payload.get("reqs", [])
    anchor = payload.get("anchor", {})
    client = create_ai_client(
        provider,
        model=payload.get("model", provider.get("image_model", "")),
        title_model=payload.get("title_model"),
        vision_model=payload.get("vision_model"),
    )
    results = []
    errors = []
    item_results = []
    total = len(reqs)
    for i, req in enumerate(reqs):
        execution.raise_if_stopped()
        item_index = int(req.get("_batch_index") or i + 1)
        req_snapshot = copy.deepcopy(req)
        prompt = req.get("final_prompt", "") if is_suite_task else ""
        error_meta = None
        img = None
        file_path = ""
        output_metadata = None
        item_refs = refs
        if is_suite_task:
            try:
                item_refs = load_image_paths(req.get("image_paths", []))
                if not item_refs:
                    raise ReferenceImageLoadError(
                        "任务参考图已丢失，请重新上传"
                    )
            except Exception as e:
                error_meta = _classify_local_image_task_error(
                    str(e),
                    "reference_load_error",
                    "任务参考图已丢失，请重新上传",
                    provider,
                )
                safe_exception = RuntimeError(error_meta["error"]).with_traceback(
                    e.__traceback__
                )
                logger.error(
                    "task combo reference loading failed (task_id=%s, item=%s)",
                    task.get("id"),
                    item_index,
                    exc_info=(RuntimeError, safe_exception, e.__traceback__),
                )
        if error_meta is None:
            try:
                if not is_suite_task:
                    prompt = client.compose_image_prompt(
                        anchor,
                        req,
                        payload.get("aspect", "1:1"),
                        payload.get("image_language", DEFAULT_TARGET_LANGUAGE),
                    )
                img = client.generate_image(
                    item_refs,
                    prompt,
                    payload.get("aspect", "1:1"),
                    payload.get("size", "1K"),
                    payload.get("thinking_level", "high"),
                    payload.get("image_language", DEFAULT_TARGET_LANGUAGE),
                )
            except Exception as e:
                error_meta = classify_provider_image_task_error(str(e), provider)
                safe_exception = RuntimeError(error_meta["error"]).with_traceback(
                    e.__traceback__
                )
                logger.error(
                    "task combo image generation failed (task_id=%s, item=%s)",
                    task.get("id"),
                    item_index,
                    exc_info=(RuntimeError, safe_exception, e.__traceback__),
                )
                client.last_error = error_meta["error"]
        if img and is_suite_task:
            try:
                stem = f"{task['id']}_{str(item_index).zfill(2)}"
                output_metadata = normalize_suite_image(
                    img,
                    DATA_DIR / "task_results",
                    stem,
                )
                file_path = output_metadata["path"]
            except Exception as e:
                error_meta = _classify_local_image_task_error(
                    str(e),
                    "output_normalization_error",
                    "套图成品规范化失败",
                    provider,
                )
                safe_exception = RuntimeError(error_meta["error"]).with_traceback(
                    e.__traceback__
                )
                logger.error(
                    "task combo output normalization failed (task_id=%s, item=%s)",
                    task.get("id"),
                    item_index,
                    exc_info=(RuntimeError, safe_exception, e.__traceback__),
                )
        if img and not is_suite_task:
            filename = (
                f"{task['id']}_{str(item_index).zfill(2)}_"
                f"{req.get('type_name', 'image')}.png"
            )
            file_path = persist_image_for_task(img, filename)
        if file_path:
            results.append(file_path)
            item_result = {
                "index": item_index,
                "type_name": req.get("type_name", "图片"),
                "status": "done",
                "file_path": file_path,
            }
            if is_suite_task:
                item_result.update(
                    {
                        "id": req.get("id", ""),
                        "type_key": req.get("type_key", ""),
                        "prompt": prompt,
                        "req": req_snapshot,
                        "output_metadata": copy.deepcopy(output_metadata),
                    }
                )
            item_results.append(item_result)
        else:
            if error_meta is None:
                error_meta = classify_provider_image_task_error(
                    client.get_last_error()
                    or f"{req.get('type_name', '图片')} 生成失败",
                    provider,
                )
            errors.append(error_meta["error"])
            item_result = {
                "index": item_index,
                "type_name": req.get("type_name", "图片"),
                "prompt": prompt,
                "req": req_snapshot,
                "status": "error",
                **error_meta,
            }
            if is_suite_task:
                item_result.update(
                    {
                        "id": req.get("id", ""),
                        "type_key": req.get("type_key", ""),
                    }
                )
            item_results.append(item_result)
        execution.checkpoint(
            progress={"done": i + 1, "total": total},
            result_files=results,
            errors=errors,
            item_results=item_results,
        )
    titles = []
    if payload.get("enable_title") and payload.get("title_info"):
        title_result = client.generate_titles(
            payload.get("title_info", ""),
            payload.get("template_prompt"),
            payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
        )
        if title_result.get("success"):
            titles = merge_titles_and_issues(title_result)
        else:
            errors.append(format_title_error(title_result))
    return {
        "titles": titles,
        "errors": errors,
        "files": results,
        "item_results": item_results,
        "partial": bool(errors),
        "target_language": payload.get("title_language", DEFAULT_TARGET_LANGUAGE),
    }


def _execute_text_to_image_task(execution: TaskExecution):
    task = execution.task
    payload = task.get("payload", {}) or {}
    provider = get_provider_by_id(payload.get("provider_id", "")) or get_active_provider()
    if not provider or not provider.get("api_key"):
        raise Exception("未配置可用的提供商")
    client = create_ai_client(provider, model=payload.get("model", ""))
    execution.checkpoint(progress={"done": 0, "total": 1})
    image = client.generate_image(
        [], payload.get("prompt", ""), payload.get("aspect", "1:1"),
        payload.get("size", "1K"), payload.get("thinking_level", "high"), "zh",
    )
    if not image:
        raise Exception(client.get_last_error() or "API 未返回图片数据")
    filename = f"{task['id']}_text_to_image.png"
    file_path = persist_image_for_task(image, filename)
    item_results = [
        {
            "index": 1,
            "type_name": "文生图",
            "status": "done",
            "file_path": file_path,
        }
    ]
    execution.checkpoint(
        progress={"done": 1, "total": 1},
        result_files=[file_path],
        item_results=item_results,
    )
    return {
        "titles": [],
        "errors": [],
        "files": [file_path],
        "item_results": item_results,
        "target_language": "zh",
    }


def _validate_image_task_payload(payload: dict):
    if not payload.get("image_paths"):
        return ["任务图片已丢失，请重新上传"]
    return []


def _validate_smart_task_payload(payload: dict):
    errors = list(_validate_image_task_payload(payload))
    if payload.get("retry_items"):
        return errors
    _, instruction_error = validate_smart_generation_instruction(
        payload.get("user_instruction", ""),
        str(payload.get("compliance_mode") or "strict"),
        user_id=payload.get("compliance_user_id"),
    )
    if instruction_error:
        errors.append(instruction_error)
    return errors


def _validate_suite_task_snapshot(payload: dict) -> list[str]:
    errors = []
    plan = payload.get("suite_plan")
    if not isinstance(plan, Mapping):
        return ["套图计划已丢失"]

    assets = plan.get("assets")
    asset_by_id = {}
    ordered_asset_ids = []
    if not isinstance(assets, list):
        errors.append("suite_plan.assets 必须是有效列表")
    else:
        for index, asset in enumerate(assets, start=1):
            asset_id = asset.get("id") if isinstance(asset, Mapping) else None
            if not isinstance(asset_id, str) or not asset_id.strip():
                errors.append(f"第 {index} 个套图素材记录无效")
            elif asset_id in asset_by_id:
                errors.append(f"套图素材 ID 重复：{asset_id}")
            else:
                asset_by_id[asset_id] = asset
                ordered_asset_ids.append(asset_id)

    plan_items = plan.get("plan_items")
    plan_item_by_id = {}
    if not isinstance(plan_items, list):
        errors.append("suite_plan.plan_items 必须是有效列表")
    else:
        validation_paths = {asset_id: asset_id for asset_id in asset_by_id}
        for index, item in enumerate(plan_items, start=1):
            item_id = item.get("id") if isinstance(item, Mapping) else None
            if not isinstance(item_id, str) or not item_id.strip():
                errors.append(f"第 {index} 个套图计划项记录无效")
                continue
            if item_id in plan_item_by_id:
                errors.append(f"套图计划项 ID 重复：{item_id}")
                continue
            plan_item_by_id[item_id] = item
            try:
                _build_suite_task_request(item, validation_paths, index)
            except ValueError as exc:
                errors.append(f"套图计划项 {item_id} 无效：{exc}")

    durable_image_paths = payload.get("image_paths")
    durable_paths_valid = isinstance(durable_image_paths, list) and not any(
        not isinstance(path, str) or not path.strip()
        for path in durable_image_paths or []
    )
    if not durable_paths_valid:
        errors.append("套图任务 image_paths 必须是有效列表")
        durable_image_paths = []
    durable_path_set = set(durable_image_paths)
    if len(durable_path_set) != len(durable_image_paths):
        errors.append("套图任务 image_paths 必须保持唯一")
    assets_complete = isinstance(assets, list) and len(ordered_asset_ids) == len(assets)
    if assets_complete and len(durable_image_paths) != len(ordered_asset_ids):
        errors.append("套图素材与 image_paths 数量必须一致")
    canonical_asset_paths = {}
    if (
        assets_complete
        and durable_paths_valid
        and len(durable_path_set) == len(durable_image_paths)
        and len(durable_image_paths) == len(ordered_asset_ids)
    ):
        canonical_asset_paths = dict(zip(ordered_asset_ids, durable_image_paths))

    canonical_req_by_id = {}
    if canonical_asset_paths:
        try:
            canonical_reqs = build_suite_task_requests(plan, canonical_asset_paths)
            canonical_req_by_id = {req["id"]: req for req in canonical_reqs}
        except ValueError:
            pass

    reqs = payload.get("reqs")
    if not isinstance(reqs, list) or not reqs:
        errors.append("套图任务 reqs 必须是非空列表")
        return errors

    req_by_id = {}
    observed_asset_paths = {}
    asset_ids_by_path = {}
    request_parts = []
    for index, req in enumerate(reqs, start=1):
        if not isinstance(req, Mapping):
            errors.append(f"第 {index} 个套图请求格式无效")
            continue
        req_id = req.get("id")
        valid_req_id = (
            req_id if isinstance(req_id, str) and req_id.strip() else None
        )
        if valid_req_id is None:
            errors.append(f"第 {index} 个套图请求缺少有效 ID")
        elif valid_req_id in req_by_id:
            errors.append(f"套图请求 ID 重复：{valid_req_id}")
        else:
            req_by_id[valid_req_id] = req

        reference_ids = req.get("reference_asset_ids")
        reference_paths = req.get("image_paths")
        references_valid = (
            isinstance(reference_ids, list)
            and 1 <= len(reference_ids) <= 3
            and all(
                isinstance(asset_id, str) and asset_id.strip()
                for asset_id in reference_ids
            )
            and len(set(reference_ids)) == len(reference_ids)
        )
        if not references_valid:
            errors.append(
                f"第 {index} 个套图请求的引用素材 ID 必须为 1 至 3 个非空唯一值"
            )
        paths_valid = (
            isinstance(reference_paths, list)
            and references_valid
            and len(reference_paths) == len(reference_ids)
            and all(
                isinstance(path, str) and path.strip() for path in reference_paths
            )
        )
        if not paths_valid:
            errors.append(f"第 {index} 个套图请求必须包含 1 至 3 张参考图")
        if not references_valid or not paths_valid:
            request_parts.append((valid_req_id, req, None))
            continue

        unknown_ids = [
            asset_id for asset_id in reference_ids if asset_id not in asset_by_id
        ]
        if unknown_ids:
            errors.append(
                f"第 {index} 个套图请求引用了未知素材：{unknown_ids[0]}"
            )
        for asset_id, path in zip(reference_ids, reference_paths):
            if path not in durable_path_set:
                errors.append(f"第 {index} 个套图请求引用了未持久化的参考图")
            canonical_path = canonical_asset_paths.get(asset_id)
            if canonical_path is not None and canonical_path != path:
                errors.append(f"套图素材 {asset_id} 的持久化路径映射冲突")
            observed_path = observed_asset_paths.get(asset_id)
            if observed_path is not None and observed_path != path:
                errors.append(f"套图素材 {asset_id} 的持久化路径映射冲突")
            else:
                observed_asset_paths[asset_id] = path
            existing_asset_id = asset_ids_by_path.get(path)
            if existing_asset_id is not None and existing_asset_id != asset_id:
                errors.append(
                    f"套图持久化路径重复映射到不同素材：{existing_asset_id}、{asset_id}"
                )
            else:
                asset_ids_by_path[path] = asset_id
        request_parts.append((valid_req_id, req, reference_ids))

    plan_ids = set(canonical_req_by_id or plan_item_by_id)
    req_ids = set(req_by_id)
    if payload.get("retry_parent_id"):
        if not req_ids or not req_ids.issubset(plan_ids):
            errors.append("失败项重试请求 ID 必须是原套图计划项的非空子集")
    elif req_ids != plan_ids or len(reqs) != len(plan_item_by_id):
        errors.append("首次套图请求 ID 必须与计划项完整匹配")

    for req_id, req, reference_ids in request_parts:
        expected_req = canonical_req_by_id.get(req_id)
        if expected_req is None:
            errors.append(f"套图请求 {req_id or 'unknown'} 与冻结计划不一致")
            continue
        if reference_ids is None:
            continue
        req_projection = dict(req)
        if payload.get("retry_parent_id"):
            req_projection.pop("_batch_index", None)
        if req_projection != expected_req:
            errors.append(f"套图请求 {req_id} 与冻结计划不一致")
    return errors


def _validate_combo_task_payload(payload: dict):
    errors = list(_validate_image_task_payload(payload))
    if not payload.get("reqs"):
        errors.append("没有可执行的组图项目")
    if "suite_version" not in payload:
        return errors
    if payload.get("suite_version") != SUITE_TASK_VERSION:
        errors.append("不支持的套图任务版本")
    if not isinstance(payload.get("suite_draft"), Mapping):
        errors.append("套图草稿已丢失")
    errors.extend(_validate_suite_task_snapshot(payload))
    return errors


def _validate_text_to_image_payload(payload: dict):
    return [] if str(payload.get("prompt") or "").strip() else ["请输入图片描述"]


def get_task_handlers():
    return {
        "title": TaskHandler(_execute_title_task),
        "translate": TaskHandler(
            _execute_translate_task, validate_payload=_validate_image_task_payload
        ),
        "smart": TaskHandler(
            _execute_smart_task, validate_payload=_validate_smart_task_payload
        ),
        "text_to_image": TaskHandler(
            _execute_text_to_image_task,
            validate_payload=_validate_text_to_image_payload,
        ),
        "combo": TaskHandler(
            _execute_combo_task, validate_payload=_validate_combo_task_payload
        ),
    }


CLEANUP_INTERVAL_SECONDS = 60 * 60  # 1 hour
_TASK_CLEANUP_LOCK = threading.RLock()
_TASK_LAST_CLEANUP_TS = 0.0


def maybe_run_periodic_cleanup():
    """Run trashed-record cleanup on the task engine's maintenance cadence."""
    global _TASK_LAST_CLEANUP_TS
    now_ts = time.time()
    with _TASK_CLEANUP_LOCK:
        if now_ts - _TASK_LAST_CLEANUP_TS < CLEANUP_INTERVAL_SECONDS:
            return
        _TASK_LAST_CLEANUP_TS = now_ts
    try:
        cleanup_expired_trashed_records()
    except Exception:
        logger.exception("periodic trashed-record cleanup failed")
    try:
        TASK_REPOSITORY.prune_expired_runners()
    except Exception:
        logger.exception("periodic task-runner cleanup failed")


def _run_task_maintenance():
    maybe_run_periodic_cleanup()
    repair_unarchived_task_history()


@st.cache_resource(show_spinner=False)
def get_task_engine():
    return TaskEngine(
        TASK_REPOSITORY,
        get_task_handlers(),
        runner_id=_task_runner_id(),
        max_running=lambda: get_task_limits()[0],
        terminal_callback=record_task_history,
        maintenance_callback=_run_task_maintenance,
        error_sanitizer=sanitize_task_error,
        lease_seconds=TASK_RUNNER_LEASE_SECONDS,
        heartbeat_seconds=TASK_RUNNER_HEARTBEAT_SECONDS,
        supervisor_interval_seconds=TASK_SUPERVISOR_INTERVAL_SECONDS,
        logger=logger,
    )


def run_task_worker(task_id: str, claim_token: str):
    return get_task_engine().run_claimed(task_id, claim_token)


def schedule_task_workers():
    return get_task_engine().schedule()


def ensure_task_supervisor():
    return get_task_engine().start()


def build_task_item_views(task: dict) -> list:
    task = task or {}
    raw_items = task.get("item_results", []) or []
    result_files = [str(path) for path in task.get("result_files", []) or [] if path]
    progress = task.get("progress", {}) or {}
    try:
        declared_total = max(0, int(progress.get("total") or 0))
    except (TypeError, ValueError):
        declared_total = 0

    task_status = str(task.get("status") or "queued")
    missing_status = {
        "running": "pending",
        "done": "done",
        "partial": "error",
        "error": "error",
        "cancelled": "cancelled",
        "expired": "expired",
    }.get(task_status, "pending")
    status_aliases = {
        "success": "done",
        "completed": "done",
        "failed": "error",
        "failure": "error",
        "queued": "pending",
    }
    allowed_statuses = {
        "pending",
        "running",
        "done",
        "error",
        "cancelled",
        "expired",
    }

    items_by_index = {}
    represented_files = set()
    next_index = 1
    for position, raw_item in enumerate(raw_items, start=1):
        item = raw_item if isinstance(raw_item, dict) else {}
        try:
            index = int(item.get("index") or position)
        except (TypeError, ValueError):
            index = position
        if index <= 0 or index in items_by_index:
            while next_index in items_by_index:
                next_index += 1
            index = next_index
        raw_status = str(item.get("status") or missing_status).strip().lower()
        status = status_aliases.get(raw_status, raw_status)
        if status not in allowed_statuses:
            status = missing_status
        file_path = str(item.get("file_path") or "")
        if file_path:
            represented_files.add(file_path)
        items_by_index[index] = {
            "index": index,
            "label": str(item.get("type_name") or item.get("label") or f"第 {index} 项"),
            "status": status,
            "file_path": file_path,
            "error": str(item.get("error") or ""),
        }

    for file_number, file_path in enumerate(result_files, start=1):
        if file_path in represented_files:
            continue
        index = 1
        while index in items_by_index:
            index += 1
        items_by_index[index] = {
            "index": index,
            "label": f"图片 {file_number}",
            "status": "done",
            "file_path": file_path,
            "error": "",
        }

    highest_index = max(items_by_index, default=0)
    if declared_total and highest_index > declared_total:
        items_by_index = {
            display_index: {**item, "index": display_index}
            for display_index, item in enumerate(
                (items_by_index[index] for index in sorted(items_by_index)),
                start=1,
            )
        }
        highest_index = max(items_by_index, default=0)
    total = max(declared_total, highest_index)
    for index in range(1, total + 1):
        items_by_index.setdefault(
            index,
            {
                "index": index,
                "label": f"第 {index} 项",
                "status": missing_status,
                "file_path": "",
                "error": "",
            },
        )
    return [items_by_index[index] for index in sorted(items_by_index)]


def render_task_item_results(task: dict, show_images: bool) -> None:
    items = build_task_item_views(task)
    if not items:
        return
    status_labels = {
        "pending": "等待中",
        "running": "处理中",
        "done": "成功",
        "error": "失败",
        "cancelled": "已取消",
        "expired": "已中断",
    }
    if not show_images:
        st.caption(
            "逐项："
            + " · ".join(
                f"{item['label']} {status_labels.get(item['status'], item['status'])}"
                for item in items
            )
        )
        return

    for start in range(0, len(items), 4):
        columns = st.columns(4)
        for column, item in zip(columns, items[start : start + 4]):
            with column:
                status_label = status_labels.get(item["status"], item["status"])
                file_path = item.get("file_path", "")
                if file_path and Path(file_path).exists():
                    st.image(
                        file_path,
                        caption=f"{status_label} · {item['label']}",
                        width="stretch",
                    )
                else:
                    st.caption(f"{status_label} · {item['label']}")
                    if item["status"] == "done" and file_path:
                        st.caption("结果文件暂不可用")
                if item.get("error"):
                    st.caption("原因：" + sanitize_task_error(item["error"]))


def render_task_center():
    tasks = list_tasks_for_display()
    records = list_active_history_records(owner_id=get_session_owner_id())
    trashed_records = list_trashed_history_records(owner_id=get_session_owner_id())
    st.markdown("#### 📡 任务状态")
    if not tasks and not records and not trashed_records:
        st.caption("当前没有任务")
        return
    queued = sum(task.get("status") == "queued" for task in tasks)
    running = sum(task.get("status") == "running" for task in tasks)
    completed_records = [r for r in records if r.get("status") == "done"]
    if queued or running:
        st.caption(f"运行中 {running} · 排队中 {queued}")
    elif completed_records:
        st.caption(f"当前无活动任务 · 已完成 {len(completed_records)}")
    else:
        st.caption("当前没有活动任务")


def render_failed_task_retry_controls(
    task: dict,
    retry_providers: list,
    active_provider_id: str,
) -> None:
    retryable_items = get_retryable_failed_items(task)
    wait_seconds = failed_item_retry_wait_seconds(task)
    if wait_seconds:
        st.caption(f"上游正在冷却，约 {wait_seconds} 秒后可重试失败项。")
    else:
        st.caption("冷却已结束，可以仅重试失败项，不会重跑成功图片。")

    selected_provider_id = ""
    selected_model = ""
    if retry_providers:
        provider_ids = [provider.get("id", "") for provider in retry_providers]
        payload = task.get("payload") or {}
        task_provider_id = str(payload.get("provider_id") or "")
        default_provider_id = active_provider_id
        if default_provider_id not in provider_ids:
            default_provider_id = (
                task_provider_id
                if task_provider_id in provider_ids
                else provider_ids[0]
            )
        provider_key = f"task_center_retry_provider_{task.get('id')}"
        if st.session_state.get(provider_key) not in provider_ids:
            st.session_state[provider_key] = default_provider_id
        selected_provider_id = st.selectbox(
            "重试提供商",
            provider_ids,
            key=provider_key,
            format_func=lambda provider_id: next(
                (
                    provider.get("name", provider_id)
                    for provider in retry_providers
                    if provider.get("id") == provider_id
                ),
                provider_id,
            ),
            help="失败任务原本固定使用提交时的接口；这里可以明确改用当前或备用提供商。",
        )
        selected_provider = next(
            (
                provider
                for provider in retry_providers
                if provider.get("id") == selected_provider_id
            ),
            {},
        )
        model_choices = _provider_model_choices(selected_provider, "image")
        task_model = str(payload.get("model") or "")
        default_model = str(selected_provider.get("image_model") or "")
        if selected_provider_id == task_provider_id and task_model:
            default_model = task_model
        if default_model and default_model not in model_choices:
            model_choices.append(default_model)
        if model_choices:
            model_key = f"task_center_retry_model_{task.get('id')}"
            if st.session_state.get(model_key) not in model_choices:
                st.session_state[model_key] = default_model or model_choices[0]
            model_labels = _provider_model_labels(selected_provider, "image")
            selected_model = st.selectbox(
                "重试出图模型",
                model_choices,
                key=model_key,
                format_func=lambda model_id: model_labels.get(model_id, model_id),
            )
    else:
        st.warning("没有已启用且配置了 API Key 的出图提供商。")

    if st.button(
        f"重试失败项 ({len(retryable_items)})",
        key=f"task_center_retry_failed_{task.get('id')}",
        disabled=bool(wait_seconds) or not selected_provider_id,
    ):
        retry_task, error = retry_failed_task_items(
            task.get("id"),
            provider_id=selected_provider_id,
            model=selected_model,
        )
        if retry_task:
            open_submitted_task(retry_task)
        else:
            st.error(error or "创建重试任务失败")


def show_task_center():
    st.markdown('<div class="page-title">📡 任务中心</div>', unsafe_allow_html=True)
    submission_notice = st.session_state.pop("task_submission_notice", "")
    if submission_notice:
        st.success(submission_notice)
    st.caption("提交后的任务会在后台继续执行。你可以随时离开本页并开始新任务，结果完成后会自动归档到项目中心。")
    if st.button("刷新进度", key="task_center_refresh"):
        st.rerun()
    tasks = list_tasks_for_display()
    active = [task for task in tasks if build_task_center_state(task)["can_cancel"]]
    terminal = [task for task in tasks if task.get("status") in TASK_TERMINAL_STATUSES]
    queued = sum(task.get("status") == "queued" for task in active)
    running = sum(task.get("status") == "running" for task in active)

    m1, m2, m3 = st.columns(3)
    m1.metric("运行中", running)
    m2.metric("排队中", queued)
    m3.metric("最近完成", sum(task.get("status") == "done" for task in terminal))
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✨ 新建文字生图", type="primary", width="stretch"):
            set_nav_page("✨ 文字生图")
            st.rerun()
    with c2:
        if st.button("🎨 新建素材出图", width="stretch"):
            set_nav_page("🎨 快速出图 / 图片翻译")
            st.rerun()
    with c3:
        if st.button("📚 查看项目结果", width="stretch"):
            set_nav_page(PROJECT_CENTER_PAGE)
            st.rerun()

    active_tab, recent_tab = st.tabs(["🚧 进行中与排队", "🕘 最近任务"])
    with active_tab:
        if not active:
            st.info("当前没有运行或排队中的任务。可以直接开始一个新任务。")
        for task in active:
            progress = task.get("progress", {}) or {}
            total = max(1, int(progress.get("total") or 1))
            done = min(total, int(progress.get("done") or 0))
            task_summary = build_task_display_summary(task)
            with st.container(border=True):
                left, right = st.columns([5, 1])
                with left:
                    st.markdown(
                        f"**{_task_status_label(task.get('status'))} · {task_summary}**"
                    )
                    if task.get("status") == "running":
                        st.progress(done / total, text=f"进度 {done}/{total}")
                    else:
                        st.caption("等待可用执行槽位")
                    st.caption(build_task_route_summary(task))
                    if task.get("item_results"):
                        render_task_item_results(task, show_images=False)
                with right:
                    if st.button("取消", key=f"task_center_cancel_{task.get('id')}", width="stretch"):
                        cancel_task(task.get("id"))
                        st.rerun()
    with recent_tab:
        if not terminal:
            st.info("提交过的任务会显示在这里。")
        retry_providers = get_retry_image_providers()
        active_retry_provider_id = str(
            (get_active_provider() or {}).get("id") or ""
        )
        for task in terminal[:12]:
            item_views = build_task_item_views(task)
            progress = task.get("progress", {}) or {}
            task_summary = build_task_display_summary(task)
            success_count = sum(item["status"] == "done" for item in item_views)
            failed_count = sum(item["status"] == "error" for item in item_views)
            if not item_views:
                success_count = int(
                    progress.get("success") or len(task.get("result_files", []) or [])
                )
                failed_count = int(
                    progress.get("failed") or len(task.get("errors", []) or [])
                )
            with st.container(border=True):
                st.caption(
                    f"{_task_status_label(task.get('status'))} · {task_summary} · "
                    f"{task.get('updated_at', '')}"
                )
                st.caption(build_task_route_summary(task))
                if success_count or failed_count:
                    st.caption(f"结果：成功 {success_count} · 失败 {failed_count}")
                if task.get("errors"):
                    st.caption(
                        "原因：" + format_task_error_summary(task.get("errors"), 1)
                    )
                if timeout_diagnostic := build_task_timeout_diagnostic(task):
                    st.caption(timeout_diagnostic)
                render_task_item_results(task, show_images=True)
                task_center_state = build_task_center_state(task)
                if task_center_state["can_retry_failed_items"]:
                    render_failed_task_retry_controls(
                        task,
                        retry_providers,
                        active_retry_provider_id,
                    )

    show_footer()


def set_nav_page(page: str):
    st.session_state["nav_page"] = page


def open_submitted_task(task: dict):
    """Use one post-submit path so every workflow lands in the task center."""
    st.session_state["task_submission_notice"] = (
        f"任务已提交并在后台运行：{task.get('id', '')}"
    )
    set_nav_page(TASK_CENTER_PAGE)
    st.rerun()


def get_nav_page():
    current = st.session_state.get("nav_page", MAIN_NAV_ITEMS[0])
    if current == "🎨 快速出图":
        current = "🎨 快速出图 / 图片翻译"
    allowed = set(MAIN_NAV_ITEMS + MANAGEMENT_NAV_ITEMS + [PROJECT_CENTER_PAGE, TASK_CENTER_PAGE])
    if current not in allowed:
        current = MAIN_NAV_ITEMS[0]
    st.session_state["nav_page"] = current
    return current


def render_sidebar_nav_section(title: str, items: list, current_page: str):
    st.markdown(f"#### {title}")
    next_page = current_page
    for item in items:
        button_type = "primary" if item == current_page else "secondary"
        if st.button(item, key=f"nav_{title}_{item}", width="stretch", type=button_type):
            if item != current_page:
                set_nav_page(item)
                st.rerun()
            next_page = item
    return next_page


def render_status_center_content():
    tasks = list_tasks_for_display()
    active_tasks = [task for task in tasks if task.get("status") in {"queued", "running"}]
    active_records = list_active_history_records(owner_id=get_session_owner_id())
    recent_done = [record for record in active_records if record.get("status") == "done"][:3]
    recent_error = [record for record in active_records if record.get("status") == "error"][:3]

    st.caption(f"进行中 {len(active_tasks)} · 历史 {len(active_records)} · 回收站 {len(list_trashed_history_records(owner_id=get_session_owner_id()))}")
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

    if st.button("打开完整项目中心", key="status_center_open_project", width="stretch"):
        set_nav_page(PROJECT_CENTER_PAGE)
        st.rerun()


def render_global_toolbar(current_page: str):
    left, mid, right = st.columns([5, 2, 2])
    with left:
        page_label = current_page if current_page != PROJECT_CENTER_PAGE else "📡 状态中心 / 项目中心"
        st.caption(f"当前区域: {page_label}")
    with mid:
        if hasattr(st, "popover"):
            with st.popover("📡 状态中心", width="stretch"):
                render_status_center_content()
        elif st.button("📡 状态中心", key="status_center_fallback", width="stretch"):
            set_nav_page(PROJECT_CENTER_PAGE)
            st.rerun()
    with right:
        if st.button("📚 项目中心", key="toolbar_project_center", width="stretch"):
            set_nav_page(PROJECT_CENTER_PAGE)
            st.rerun()


def _record_status_label(status: str):
    return {
        "done": "🟢 已完成",
        "partial": "🟠 部分完成",
        "error": "🔴 失败",
        "cancelled": "⚫ 已取消",
        "expired": "🟠 已过期",
    }.get(status, status or "unknown")


def _task_status_label(status: str):
    return {
        "queued": "🟡 排队中",
        "running": "🔵 执行中",
        "done": "🟢 已完成",
        "partial": "🟠 部分完成",
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
            st.warning(format_task_error_summary(record.get("errors"), 3))

        if zip_path and Path(zip_path).exists() and not in_trash:
            zip_prep_key = f"zipprep_{record.get('task_id')}"
            if not st.session_state.get(zip_prep_key):
                if st.button(
                    "📦 准备下载 ZIP",
                    key=f"hist_zip_prep_{record.get('task_id')}",
                ):
                    st.session_state[zip_prep_key] = True
                    st.rerun()
            else:
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
                    if not record_owned_by_session(record):
                        st.warning("该记录属于其他会话，无法操作")
                        st.stop()
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
                if not record_owned_by_session(record):
                    st.warning("该记录属于其他会话，无法操作")
                    st.stop()
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
                        open_submitted_task(relaunched_task)
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
                if not record_owned_by_session(record):
                    st.warning("该记录属于其他会话，无法操作")
                    st.stop()
                trashed = trash_history_record(record.get("task_id"))
                if trashed:
                    st.success("已移入回收站")
                    st.rerun()

        if record.get("input_file_paths"):
            st.caption(f"可重发素材: {len(record.get('input_file_paths', []))} 个")

        if files:
            # 历史项目也使用固定预览网格，避免一张大图撑满展开区域。
            preview_cols = st.columns(4)
            for idx, file_path in enumerate(files[:4]):
                p = Path(file_path)
                if p.exists():
                    with preview_cols[idx % len(preview_cols)]:
                        try:
                            st.image(
                                Image.open(p),
                                caption=p.name,
                                width="stretch",
                            )
                        except Exception:
                            st.caption(p.name)

        if titles:
            st.markdown("##### 标题内容")
            st.code(format_titles_text(titles), language="text")


def render_file_management_tab(records: list):
    if startup_notice := st.session_state.pop("startup_maintenance_notice", ""):
        st.success(startup_notice)
    if not records:
        st.info("还没有可管理的项目文件。完成一次出图后，结果文件会出现在这里。")
    orphan_dirs = find_orphan_project_dirs(records)
    summaries = {
        id(record): summarize_record_files(record) for record in records
    }
    total_size = sum(s["size_bytes"] for s in summaries.values())
    missing_records = [
        record for record in records if summaries[id(record)]["missing_count"]
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
        summary = summaries.get(id(record)) or summarize_record_files(record)
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

    tasks = list_tasks_for_display()
    active_records = list_active_history_records(owner_id=get_session_owner_id())
    trashed_records = list_trashed_history_records(owner_id=get_session_owner_id())
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
                    st.warning(format_task_error_summary(task.get("errors"), 3))
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
                removed_tasks = clear_completed_tasks()
                moved_records = len(trash_history_records_by_status({"done"}))
                st.session_state["project_center_notice"] = (
                    f"已清理 {removed_tasks} 条队列记录，并将 {moved_records} 条已完成项目移入回收站。"
                )
                st.rerun()
        if notice := st.session_state.pop("project_center_notice", ""):
            st.success(notice)
        if not active_records:
            st.info("还没有历史项目。出图任务完成或失败后会自动出现在这里，可随时回来下载结果。")
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
def consume_combo_generation_request(provider, model_key, state=None):
    state = st.session_state if state is None else state
    if not state.get("combo_generating"):
        return None, ""

    state["combo_generating"] = False
    combo_images = state.get("combo_images", [])
    image_paths = _save_uploaded_images(
        combo_images, f"combo_{int(time.time())}"
    )
    suite_plan = state.get("combo_suite_plan")
    suite_draft = state.get("combo_suite_draft")
    suite_payload = {}
    if suite_plan is not None or suite_draft is not None:
        if not isinstance(suite_plan, Mapping) or not isinstance(suite_draft, Mapping):
            return None, "套图草稿或已批准计划已丢失，请重新生成出图计划。"
        plan_assets = suite_plan.get("assets", [])
        if not isinstance(plan_assets, list) or len(plan_assets) != len(image_paths):
            return None, "套图素材持久化不完整，请重新上传素材。"
        persisted_assets = [
            {"id": asset.get("id"), "path": path}
            for asset, path in zip(plan_assets, image_paths)
            if isinstance(asset, Mapping)
        ]
        try:
            reqs = build_suite_task_requests(suite_plan, persisted_assets)
        except ValueError as exc:
            return None, str(exc)
        suite_payload = {
            "suite_version": SUITE_TASK_VERSION,
            "suite_draft": copy.deepcopy(suite_draft),
            "suite_plan": copy.deepcopy(suite_plan),
        }
    else:
        reqs = state.get("combo_reqs", [])

    default_title_model = resolve_default_title_vision_model(
        provider.get("title_model") or provider.get("vision_model", "")
    )
    return create_task(
        "combo",
        {
            **suite_payload,
            "provider_id": provider.get("id", ""),
            "anchor": state.get("combo_anchor"),
            "reqs": reqs,
            "image_paths": image_paths,
            "total": len(reqs),
            "image_language": state.get(
                "combo_image_language", DEFAULT_TARGET_LANGUAGE
            ),
            "model": state.get("combo_output_model", model_key),
            "aspect": state.get("combo_aspect", "1:1"),
            "size": state.get("combo_size", "1K"),
            "thinking_level": state.get("combo_thinking_level", "high"),
            "enable_title": state.get("combo_enable_title", False),
            "title_info": state.get("combo_title_info", ""),
            "template_prompt": "",
            "title_language": state.get(
                "combo_title_language", DEFAULT_TARGET_LANGUAGE
            ),
            "title_model": state.get("combo_title_vision_model", default_title_model),
            "vision_model": state.get(
                "combo_title_vision_model", default_title_model
            ),
            "summary": f"智能组图任务 · {len(reqs)}张",
        },
    )


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

    # 侧边栏：只保留只读的任务状态/用量信息，可交互的出图参数已移到主区域「这次出图设置」卡片
    model_key = provider_image_model or s.get("default_model", "nano-banana")
    with st.sidebar:
        st.markdown("#### 📊 任务状态")
        if st.session_state.combo_anchor:
            a = st.session_state.combo_anchor
            st.markdown(
                f'<div class="success-card" style="font-size:13px"><strong>🎯 {esc(a.get("product_name_zh", "商品"))}</strong><br><span style="color:#64748b">品类: {esc(a.get("primary_category", "未识别"))}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("📤 请先上传并分析商品")

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

        if st.button("🔄 开始新任务", type="primary", width="stretch"):
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
        st.caption("支持 PNG / JPG / WEBP，可多选。上传后系统会先分析商品，再按所选类型批量出图。")

        if files:
            images = []
            display_count = min(len(files), 6)
            # 固定预览网格，单张上传不会占满整个内容区。
            cols = st.columns(min(max(display_count, 3), 6))
            for i, f in enumerate(files[:display_count]):
                img = Image.open(f).convert("RGB")
                images.append(img)
                with cols[i]:
                    st.image(img, caption=f"图{i + 1}", width="stretch")
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
            width="stretch",
            disabled=btn_disabled,
        ):
            with st.spinner("🤖 AI正在分析..."):
                try:
                    client = create_ai_client(provider, model=model_key)
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

            enable_title, title_info, title_template, title_language, title_vision_model = (
                render_title_gen_option("combo", provider)
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
            output_settings = render_output_settings_panel("combo", provider, s)
            model_key = output_settings["model"]

            can_generate = total_count > 0 and total_count <= MAX_TOTAL_IMAGES

            if st.button(
                "📝 AI生成图需文案",
                type="primary",
                width="stretch",
                disabled=not can_generate,
            ):
                with st.spinner("🤖 生成中..."):
                    try:
                        client = create_ai_client(provider, model=model_key)
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
                "🚀 确认并开始出图", type="primary", width="stretch"
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
                task_desc += " + **TEMU 三语标题（中/西/法）**"
            st.markdown(task_desc)
            if st.button("🚀 确认开始生成", type="primary", width="stretch"):
                st.session_state.combo_generating = True
                st.rerun()
        else:
            task, err = consume_combo_generation_request(provider, model_key)
            if task:
                open_submitted_task(task)
            else:
                st.error(err or "任务提交失败，请重试。")

    show_footer()


# ==================== 快速出图页面 ====================
def show_text_to_image_page():
    st.markdown('<div class="page-title">✨ 文字生图</div>', unsafe_allow_html=True)

    s = get_settings()
    provider = get_active_provider()
    if not provider or not provider.get("api_key"):
        st.error("⚠️ 未配置可用的提供商，请先在「提供商设置」中添加")
        return

    st.caption("输入提示词后直接生成图片，无需上传商品素材。")
    prompt = st.text_area(
        "图片提示词",
        key="text_to_image_prompt",
        max_chars=3000,
        height=180,
        placeholder="例如：一只戴着红色围巾的橘猫，坐在雨后的东京街头，电影感灯光，高细节",
    )
    st.caption("建议说明主体、场景、构图、光线、风格，以及图片中需要出现的文字。")

    output_settings = render_output_settings_panel("text_to_image", provider, s)
    model = output_settings["model"]
    aspect = output_settings["aspect"]
    size = output_settings["resolution"]
    thinking_level = output_settings["thinking_level"]

    generate = st.button(
        "✨ 提交生成任务",
        type="primary",
        width="stretch",
        disabled=not prompt.strip(),
    )
    if generate:
        task, error = create_task(
            "text_to_image",
            {
                "provider_id": provider.get("id", ""),
                "prompt": prompt.strip(),
                "model": model,
                "aspect": aspect,
                "size": size,
                "thinking_level": thinking_level,
                "total": 1,
                "summary": f"文字生图任务 · {prompt.strip()[:28]}",
            },
        )
        if task:
            open_submitted_task(task)
        else:
            st.error(error)

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

        if st.button("🔄 开始新任务", type="primary", width="stretch"):
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
    st.caption("支持 PNG / JPG / WEBP，可多选。上传后选择出图类型即可开始。")

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
        name = st.text_input(
            "商品名称（可选）",
            key="smart_name",
            placeholder="不填写时由 AI 根据商品图识别",
            help="仅在商品型号、品类或名称不易从图片识别时填写。",
        )
    with c2:
        material = st.text_input(
            "材质（可选）",
            key="smart_material",
            placeholder="例如：304 不锈钢",
        )
    user_instruction = ""
    name = name.strip()
    material = material.strip()

    st.markdown("---")

    if workflow_mode == "creative":
        selected_types, total_count = render_type_selector(
            templates, prefix="smart", max_per_type=5, max_total=20
        )
        user_instruction = st.text_area(
            "补充提示词（可选）",
            key="smart_user_instruction",
            max_chars=MAX_TITLE_INFO_CHARS,
            placeholder="例如：强调杯盖密封，使用干净的厨房台面场景，画面不添加额外文案",
            help="会附加到本次每一张出图的提示词中；商品本体仍以参考图为准。",
        )
        enable_title, title_info, title_template, title_language, title_vision_model = (
            render_title_gen_option("smart", provider)
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
        title_vision_model = resolve_default_title_vision_model(
            title_model or vision_model
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

    output_settings = render_output_settings_panel("smart", provider, s)
    model = output_settings["model"]
    aspect = output_settings["aspect"]
    size = output_settings["resolution"]
    thinking_level = output_settings["thinking_level"]
    compliance_mode = output_settings["compliance_mode"]

    can_gen = can_submit_smart_generation(images, workflow_mode, total_count)

    if st.button(
        "🚀 开始翻译" if workflow_mode == "translate" else "🚀 开始生成",
        type="primary",
        width="stretch",
        disabled=not can_gen,
    ):
        user_instruction, instruction_error = validate_smart_generation_instruction(
            user_instruction if workflow_mode == "creative" else "",
            compliance_mode,
        )
        if instruction_error:
            st.error(instruction_error)
            return
        image_paths = _save_uploaded_images(files or [], f"smart_{int(time.time())}")
        task, err = create_task(
            "translate" if workflow_mode == "translate" else "smart",
            {
                "provider_id": provider.get("id", ""),
                "image_paths": image_paths,
                "name": name,
                "material": material or "",
                "user_instruction": user_instruction.strip(),
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
                "template_prompt": "",
                "title_language": title_language,
                "title_model": title_vision_model,
                "vision_model": title_vision_model,
                "translation_template": translation_template,
                "compliance_mode": compliance_mode,
                "summary": build_smart_task_summary(
                    workflow_mode,
                    name,
                    total_count=total_count,
                    image_count=len(images),
                ),
            },
        )
        if task:
            open_submitted_task(task)
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

    st.markdown(
        f"""<div class="help-section">
        <h4>🎯 输出规则（TEMU 三语标题）</h4>
        <ul>
            <li><b>固定三语</b> - 每次输出 🇨🇳 中文 / 🇪🇸 Español / 🇫🇷 Français 各一条</li>
            <li><b>字符区间</b> - 中文 {TITLE_CHAR_RANGES["zh"][0]}-{TITLE_CHAR_RANGES["zh"][1]} 字符；西语/法语 {TITLE_CHAR_RANGES["es"][0]}-{TITLE_CHAR_RANGES["es"][1]} 字符（含空格）</li>
            <li><b>中文回译</b> - 西语/法语标题附中文回译，方便核对</li>
            <li><b>合规自查</b> - 按 TEMU 三层合规框架幕后自查后输出</li>
        </ul>
    </div>""",
        unsafe_allow_html=True,
    )

    title_language = DEFAULT_TARGET_LANGUAGE  # 三语标题固定输出 zh/es/fr

    st.markdown("### 🧠 标题生成模型")
    default_title_vision_model = title_model or vision_model or resolve_default_title_vision_model(
        title_model or vision_model
    )
    selected_title_vision_model = render_provider_model_select(
        "选择用于识图/生成标题的模型",
        provider,
        "vision",
        default_title_vision_model,
        key="standalone_title_vision_model",
        allow_unset=False,
    )
    st.caption("模型列表优先来自当前提供商已获取的上游目录。")
    st.caption(
        f"ℹ️ 当前提供商协议：{provider.get('provider_type', 'gemini')}；"
        f"提供商默认配置：文字生成模型 {title_model or '未配置'} · 图片理解模型 {vision_model or '未配置'}"
    )
    st.caption("当前输出: 🇨🇳 中文 + 🇪🇸 Español + 🇫🇷 Français（TEMU 三语标题）")

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
        st.caption("支持 PNG / JPG / WEBP，可多选。AI 会先识别图中商品信息，再进行标题生成。")

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

    final_prompt = ""
    st.caption("标题策略：内置 TEMU 三语生成与合规自查")

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
        width="stretch",
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
                "title_model": selected_title_vision_model,
                "vision_model": selected_title_vision_model,
                "summary": "标题任务 · TEMU 三语(中/西/法)",
            },
        )
        if task:
            open_submitted_task(task)
        else:
            st.error(err)

    show_footer()


# ==================== 主应用 ====================
def main_app():
    st.session_state["_footer_rendered"] = False
    current_page = get_nav_page()
    with st.sidebar:
        st.markdown(TULITE_LOGO_HTML, unsafe_allow_html=True)
        st.markdown("---")
        render_demo_admin_panel()
        if demo_mode_enabled():
            st.markdown("---")
        provider = get_active_provider()
        if provider:
            st.caption(f"当前提供商: {provider.get('name', '')}")
        current_page = render_sidebar_nav_section("功能区", MAIN_NAV_ITEMS, current_page)
        st.markdown("---")
        current_page = render_sidebar_nav_section("管理与配置", MANAGEMENT_NAV_ITEMS, current_page)
        st.markdown("---")
        render_task_center()

        if st.button("🚪 退出", width="stretch"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    set_nav_page(current_page)
    if demo_mode_enabled() and SERVER_MODE:
        if not st.session_state.get("_demo_server_warned"):
            logger.warning(
                "XIAOBAITU_DEMO_MODE 在 server 模式下开启：演示面板对所有访问者可见，生产环境请关闭"
            )
            st.session_state["_demo_server_warned"] = True
        st.warning(
            "⚠️ 演示模式（XIAOBAITU_DEMO_MODE）已在服务器环境开启：演示管理面板对所有访问者可见，生产环境请设置 XIAOBAITU_DEMO_MODE=0。"
        )
    render_global_toolbar(current_page)

    if current_page == "🚀 智能组图":
        show_combo_page()
    elif current_page == "✨ 文字生图":
        show_text_to_image_page()
    elif current_page == "🎨 快速出图 / 图片翻译":
        show_smart_page()
    elif current_page == "🏷️ 标题生成":
        show_title_page()
    elif current_page == TASK_CENTER_PAGE:
        show_task_center()
    elif current_page == PROJECT_CENTER_PAGE:
        show_project_center()
    elif current_page == "🧩 模板库":
        show_template_library()
    elif current_page == "⚙️ 提供商设置":
        show_provider_settings()
    else:
        show_settings_center()

    show_footer()


def require_access_password() -> None:
    """Require authentication, and fail closed for server deployments."""
    expected = os.getenv("APP_ACCESS_PASSWORD", "")
    if not expected:
        if SERVER_MODE:
            st.error(
                "服务器模式缺少 APP_ACCESS_PASSWORD，已停止访问。"
                "请设置高强度访问口令后重启服务。"
            )
            st.stop()
        return
    if st.session_state.get("auth_ok") is True:
        return
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(
            """
<div style="border:1px solid #e2e8f0;border-radius:16px;background:#f8fafc;
            padding:22px 24px 6px 24px;margin-top:14vh;text-align:center;">
"""
            + TULITE_LOGO_HTML.replace(
                'display:flex;align-items:center;', "display:flex;align-items:center;justify-content:center;"
            )
            + """
  <div style="font-size:13px;color:#64748B;margin:2px 0 4px 0;">输入访问口令以继续</div>
</div>
""",
            unsafe_allow_html=True,
        )
        pwd = st.text_input(
            "访问口令",
            type="password",
            key="_access_pwd_input",
            label_visibility="collapsed",
            placeholder="访问口令",
        )
        if st.button("进入 TuLite", width="stretch", type="primary"):
            if hmac.compare_digest(str(pwd or ""), expected):
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("口令不正确，请重试。")
    st.stop()


# ==================== 主入口 ====================
def main():
    st.set_page_config(
        page_title=BRAND_TITLE,
        page_icon="🍌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_style()
    require_access_password()
    apply_proxy_settings()
    if os.getenv("TULITE_BOOTSTRAP_SUPERVISOR", "") != "1":
        ensure_task_supervisor()
    init_session()

    main_app()


if __name__ == "__main__":
    main()
