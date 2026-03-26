from __future__ import annotations

import re


def build_fallback_anchor(name: str = "", detail: str = "") -> dict:
    product_name = str(name or "").strip() or "Product"
    detail_text = str(detail or "").strip() or "general"
    visual_attrs = [detail_text[:30]] if detail_text else ["clean design"]
    return {
        "product_name_en": product_name,
        "product_name_zh": product_name,
        "primary_category": "General",
        "visual_attrs": visual_attrs,
        "confidence": 0.3,
    }


def analyze_product_with_text_client(
    text_client,
    images,
    name: str,
    detail: str,
    prompt_template: str,
):
    default_result = build_fallback_anchor(name, detail)
    try:
        prompt = prompt_template.format(
            product_name=name or "N/A",
            product_detail=detail or "N/A",
        )
    except KeyError:
        prompt = f"""Analyze these product images and return JSON:
{{"primary_category": "category", "product_name_en": "English name", "product_name_zh": "中文名", "visual_attrs": ["attr1", "attr2"], "confidence": 0.8}}
Product name: {name or "N/A"}
Product detail: {detail or "N/A"}
Return valid JSON only."""
    text = text_client.generate_text(images, prompt, max_tokens=1200)
    result = text_client.parse_json_response(text, default_result)
    if not isinstance(result, dict):
        return default_result
    merged = dict(default_result)
    merged.update({k: v for k, v in result.items() if v})
    return merged


def generate_requirements_with_text_client(
    text_client,
    anchor: dict,
    types_counts: dict,
    templates: dict,
    prompt_template: str,
    tags=None,
):
    types_str = ", ".join(
        [
            f"{templates[k]['name']}x{v}"
            for k, v in types_counts.items()
            if k in templates
        ]
    )
    try:
        prompt = prompt_template.format(
            product_name=anchor.get("product_name_zh", "商品"),
            category=anchor.get("primary_category", "General"),
            features=", ".join(anchor.get("visual_attrs", [])[:3]),
            tags=", ".join(tags or []) if tags else "无",
            types=types_str,
        )
    except KeyError:
        return []
    text = text_client.generate_text([], prompt, max_tokens=1600)
    result = text_client.parse_json_response(text, [])
    return result if isinstance(result, list) else []


def generate_en_copy_with_text_client(
    text_client,
    anchor: dict,
    requirements: list,
    prompt_template: str,
    max_headline_chars: int = 24,
    max_subline_chars: int = 32,
    max_badge_chars: int = 16,
):
    if not requirements:
        return requirements
    req_str = "\n".join(
        [f"- {r.get('type_name', '')}: {r.get('topic', '')}" for r in requirements]
    )
    try:
        prompt = prompt_template.format(
            product_name=anchor.get("product_name_en", "Product"),
            category=anchor.get("primary_category", "General"),
            requirements=req_str,
        )
    except KeyError:
        return requirements
    text = text_client.generate_text([], prompt, max_tokens=1600)
    copies = text_client.parse_json_response(text, [])
    if not isinstance(copies, list):
        return requirements
    copy_map = {
        (c.get("type_key"), c.get("index")): c for c in copies if isinstance(c, dict)
    }
    for r in requirements:
        key = (r.get("type_key"), r.get("index"))
        if key not in copy_map:
            continue
        c = copy_map[key]
        r["headline"] = re.sub(r"[^a-zA-Z0-9\s]", "", c.get("headline", ""))[
            :max_headline_chars
        ]
        r["subline"] = re.sub(r"[^a-zA-Z0-9\s]", "", c.get("subline", ""))[
            :max_subline_chars
        ]
        r["badge"] = re.sub(r"[^a-zA-Z0-9\s]", "", c.get("badge", ""))[:max_badge_chars]
    return requirements
