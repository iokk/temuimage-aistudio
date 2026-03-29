from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, get_current_principal


router = APIRouter(prefix="/title", tags=["title"])

DEFAULT_MODEL = "gemini-3.1-pro"


class TitlePreviewRequest(BaseModel):
    product_info: str = Field(min_length=1, max_length=4000)
    extra_requirements: str = Field(default="", max_length=1000)
    tone: str = Field(default="marketplace")
    count: int = Field(default=3, ge=1, le=5)


def _keywords_from_text(*parts: str) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for token in re.findall(r"[A-Za-z0-9]+", part.lower()):
            if len(token) < 3 or token in seen:
                continue
            seen.add(token)
            words.append(token)
    return words


def _title_case(value: str) -> str:
    return " ".join(segment.capitalize() for segment in value.split())


def build_preview_titles(
    product_info: str,
    extra_requirements: str,
    tone: str,
    count: int,
) -> list[str]:
    keywords = _keywords_from_text(product_info, extra_requirements)
    primary = _title_case(" ".join(keywords[:4])) or "Product Highlight"
    detail = _title_case(" ".join(keywords[4:8])) or "Cross Border Listing"
    tone_prefix = {
        "marketplace": "Marketplace Ready",
        "premium": "Premium Detail",
        "clean": "Clean Listing",
    }.get(tone, "Marketplace Ready")

    titles = []
    for idx in range(count):
        suffix = [
            "Optimized Title",
            "Selling Point Focus",
            "Export Listing",
            "Storefront Version",
            "Catalog Version",
        ][idx]
        title = f"{tone_prefix} {primary} {detail} {suffix}".strip()
        titles.append(" ".join(title.split()))
    return titles


@router.get("/meta")
def title_meta(_principal: Principal = Depends(get_current_principal)):
    return {
        "default_model": DEFAULT_MODEL,
        "tones": ["marketplace", "premium", "clean"],
        "max_titles": 5,
    }


@router.post("/preview")
def title_preview(
    payload: TitlePreviewRequest,
    _principal: Principal = Depends(get_current_principal),
):
    titles = build_preview_titles(
        product_info=payload.product_info,
        extra_requirements=payload.extra_requirements,
        tone=payload.tone,
        count=payload.count,
    )
    return {
        "titles": titles,
        "model": DEFAULT_MODEL,
        "source": "preview",
    }
