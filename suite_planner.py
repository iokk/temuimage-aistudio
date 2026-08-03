"""Pure domain rules for ecommerce standard image suites."""

import math
import re
from collections.abc import Mapping
from types import MappingProxyType


TYPE_KEYS = (
    "main-front",
    "back-side",
    "detail",
    "scene",
    "dimension",
    "selling-point",
    "package",
    "compare",
    "steps",
)

DEFAULT_TYPE_COUNTS = MappingProxyType(
    {
        "main-front": 1,
        "back-side": 1,
        "detail": 3,
        "scene": 1,
        "dimension": 1,
        "selling-point": 1,
    }
)

TEMU_STANDARD_PROFILE = MappingProxyType(
    {
        "id": "temu-standard",
        "name": "TEMU Standard Suite",
        "default_count": 8,
        "max_count": 10,
        "min_reference_count": 1,
        "max_reference_count": 14,
        "output_size": (1600, 1600),
        "output_formats": ("PNG", "JPG"),
        "max_file_size_bytes": 2 * 1024 * 1024,
        "default_logo_enabled": False,
        "default_type_counts": DEFAULT_TYPE_COUNTS,
    }
)


ASSET_ROLES = frozenset(
    {
        "front",
        "back",
        "side",
        "detail",
        "dimension",
        "package",
        "scene",
        "unknown",
    }
)

_ROLE_ALIASES = {
    "back-side": "back",
    "rear": "back",
    "close-up": "detail",
    "closeup": "detail",
    "size": "dimension",
    "dimensions": "dimension",
    "packaging": "package",
}

_REFERENCE_ROLES = {
    "main-front": ("front", "unknown", "detail", "side", "back", "scene"),
    "back-side": ("back", "side"),
    "detail": ("detail",),
    "scene": ("scene", "front", "side", "detail", "back", "unknown"),
    "dimension": ("dimension", "front", "side", "detail", "back", "unknown"),
    "selling-point": ("detail", "front", "side", "back", "unknown"),
    "package": ("package",),
    "compare": ("front", "side", "detail", "unknown"),
    "steps": ("detail", "front", "side", "unknown"),
}

_TYPE_TITLES = {
    "main-front": "Primary product view",
    "back-side": "Back or side product view",
    "detail": "Product detail",
    "scene": "Product in use",
    "dimension": "Product dimensions",
    "selling-point": "Key selling point",
    "package": "Package contents",
    "compare": "Product comparison",
    "steps": "Product steps",
}

_VARIATION_SEEDS = (
    ("material focus", "controlled studio setting", "macro close-up", "diagonal feature framing"),
    ("functional focus", "bright product setting", "three-quarter product view", "asymmetrical negative space"),
    ("craftsmanship focus", "soft daylight setting", "side profile view", "vertical product framing"),
    ("scale focus", "minimal lifestyle setting", "eye-level product view", "layered foreground framing"),
    ("everyday use focus", "home use setting", "wide environmental view", "rule-of-thirds framing"),
    ("finish focus", "neutral tabletop setting", "top-down product view", "centered graphic framing"),
    ("comfort focus", "natural indoor setting", "low-angle product view", "leading-line framing"),
    ("durability focus", "clean work setting", "overhead product view", "close crop with full feature"),
    ("access focus", "organized storage setting", "profile product view", "balanced open-space framing"),
    ("care focus", "simple daily setting", "contextual product view", "offset product framing"),
)

_DIMENSION_FIELD_RE = re.compile(
    r"^(length|width|height|depth|diameter|thickness)"
    r"(?:_(mm|cm|m|in|inch|inches|ft|feet))?$"
)
_DIMENSION_VALUE_RE = re.compile(
    r"^(?:\d+(?:\.\d+)?|\.\d+)\s*(?:mm|cm|m|in|inch|inches|ft|feet)?$",
    re.IGNORECASE,
)
_DIMENSION_UNITS = frozenset({"mm", "cm", "m", "in", "inch", "inches", "ft", "feet"})


def _clean_text(value):
    return value.strip() if isinstance(value, str) else ""


def _normalized_role(value):
    role = _clean_text(value).lower().replace("_", "-").replace(" ", "-")
    role = _ROLE_ALIASES.get(role, role)
    return role if role in ASSET_ROLES else "unknown"


def _normalized_confidence(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return min(max(float(value), 0.0), 1.0)


def normalize_assets(raw_assets):
    """Return stable, role-normalized asset records without inventing evidence."""
    if not isinstance(raw_assets, list):
        return []

    reserved_ids = {
        _clean_text(asset.get("id"))
        for asset in raw_assets
        if isinstance(asset, Mapping) and _clean_text(asset.get("id"))
    }
    used_ids = set()
    next_index = 1
    normalized = []
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, Mapping):
            continue
        asset_id = _clean_text(raw_asset.get("id"))
        if not asset_id or asset_id in used_ids:
            while f"asset-{next_index:02d}" in reserved_ids or f"asset-{next_index:02d}" in used_ids:
                next_index += 1
            asset_id = f"asset-{next_index:02d}"
            next_index += 1
        used_ids.add(asset_id)
        quality_flags = raw_asset.get("quality_flags", [])
        normalized.append(
            {
                "id": asset_id,
                "path": _clean_text(raw_asset.get("path") or raw_asset.get("file_path")),
                "role": _normalized_role(raw_asset.get("role")),
                "role_confidence": _normalized_confidence(raw_asset.get("role_confidence")),
                "is_primary": bool(raw_asset.get("is_primary", False)),
                "quality_flags": [flag for flag in quality_flags if isinstance(flag, str)]
                if isinstance(quality_flags, (list, tuple))
                else [],
                "variant_group": _clean_text(raw_asset.get("variant_group")) or "default",
            }
        )
    return normalized


def select_reference_assets(plan_type, assets, limit=3):
    """Select up to three role-relevant asset IDs for a planned image type."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = 3
    limit = min(max(limit, 0), 3)
    if not limit or plan_type not in TYPE_KEYS:
        return []

    normalized_assets = normalize_assets(assets)
    roles = _REFERENCE_ROLES[plan_type]
    selected = []
    for role in roles:
        for asset in normalized_assets:
            if asset["role"] == role and asset["id"] not in selected:
                selected.append(asset["id"])
                if len(selected) == limit:
                    return selected
    return selected


def _meaningful_dimension_value(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, float):
        return math.isfinite(value) and value > 0
    if isinstance(value, str):
        text = value.strip()
        if not _DIMENSION_VALUE_RE.fullmatch(text):
            return False
        numeric = re.match(r"(?:\d+(?:\.\d+)?|\.\d+)", text)
        return bool(numeric and float(numeric.group()) > 0)
    if isinstance(value, Mapping):
        if set(value) - {"value", "unit"} or "value" not in value:
            return False
        unit = _clean_text(value.get("unit")).lower()
        return (not unit or unit in _DIMENSION_UNITS) and _meaningful_dimension_value(value["value"])
    return False


def _has_valid_dimension_data(dimension_data):
    if not isinstance(dimension_data, Mapping) or not dimension_data:
        return False

    found_dimension = False
    for raw_key, value in dimension_data.items():
        key = _clean_text(raw_key).lower().replace("-", "_").replace(" ", "_")
        if key == "unit":
            if _clean_text(value).lower() not in _DIMENSION_UNITS:
                return False
            continue
        if not _DIMENSION_FIELD_RE.fullmatch(key) or not _meaningful_dimension_value(value):
            return False
        found_dimension = True
    return found_dimension


def _has_dimension_evidence(draft, assets):
    dimension_data = draft.get("dimension_data") if isinstance(draft, Mapping) else None
    if _has_valid_dimension_data(dimension_data):
        return True
    return bool(select_reference_assets("dimension", [asset for asset in assets if asset["role"] == "dimension"], 1))


def _has_selling_point_evidence(draft):
    if not isinstance(draft, Mapping):
        return False
    for key in ("selling_points", "selling_point", "verified_selling_points"):
        value = draft.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, tuple)) and any(_clean_text(item) for item in value):
            return True
    return False


def _fallback_type(remaining_detail_evidence, has_selling_point_evidence):
    if remaining_detail_evidence:
        return "detail"
    if has_selling_point_evidence:
        return "selling-point"
    return "scene"


def _variation_for(type_key, occurrence):
    theme, generic_scene, generic_shot, generic_composition = _VARIATION_SEEDS[occurrence % len(_VARIATION_SEEDS)]
    if type_key == "main-front":
        return theme, f"pure white {generic_scene}", f"front {generic_shot}", generic_composition
    if type_key == "back-side":
        return theme, f"pure white {generic_scene}", f"back or side {generic_shot}", generic_composition
    if type_key == "detail":
        return theme, generic_scene, generic_shot, generic_composition
    if type_key == "dimension":
        return theme, f"clean technical {generic_scene}", f"orthographic {generic_shot}", f"measurement-led {generic_composition}"
    if type_key == "selling-point":
        return theme, generic_scene, generic_shot, generic_composition
    if type_key == "package":
        return theme, generic_scene, f"overhead {generic_shot}", f"organized contents {generic_composition}"
    if type_key == "compare":
        return theme, f"clean comparison {generic_scene}", generic_shot, generic_composition
    if type_key == "steps":
        return theme, f"clean instructional {generic_scene}", generic_shot, generic_composition
    return theme, generic_scene, generic_shot, generic_composition


def _safe_reference_assets(type_key, assets):
    references = select_reference_assets(type_key, assets)
    if references:
        return references
    return select_reference_assets("scene", assets)


def _build_deterministic_plan(draft, normalized_assets=None):
    source = draft if isinstance(draft, Mapping) else {}
    target_count = source.get("target_count", TEMU_STANDARD_PROFILE["default_count"])
    if isinstance(target_count, bool) or not isinstance(target_count, int) or not 1 <= target_count <= 10:
        target_count = TEMU_STANDARD_PROFILE["default_count"]
    counts = normalize_type_counts(source.get("selected_type_counts"), target_count)
    assets = normalized_assets if normalized_assets is not None else normalize_assets(source.get("assets"))
    detail_evidence = sum(asset["role"] == "detail" for asset in assets)
    has_selling_point_evidence = _has_selling_point_evidence(source)
    has_dimension_evidence = _has_dimension_evidence(source, assets)
    back_replacements = counts["back-side"] if not select_reference_assets("back-side", assets, 1) else 0
    dimension_replacements = counts["dimension"] if not has_dimension_evidence else 0
    reserved_detail_capacity = min(detail_evidence, back_replacements + dimension_replacements)
    native_detail_capacity = detail_evidence - reserved_detail_capacity
    type_occurrences = {type_key: 0 for type_key in TYPE_KEYS}
    plan_items = []

    for requested_type in TYPE_KEYS:
        for _ in range(counts[requested_type]):
            type_key = requested_type
            replacement_reason = ""
            if requested_type == "back-side" and back_replacements:
                type_key = _fallback_type(reserved_detail_capacity, has_selling_point_evidence)
                replacement_reason = "Back or side reference evidence is missing."
            elif requested_type == "dimension" and dimension_replacements:
                type_key = _fallback_type(reserved_detail_capacity, has_selling_point_evidence)
                replacement_reason = "Dimension data or a dimension reference is missing."
            elif requested_type == "detail" and not native_detail_capacity:
                type_key = _fallback_type(0, has_selling_point_evidence)
                replacement_reason = "A distinct visible detail reference is missing."
            elif requested_type == "package" and not select_reference_assets("package", assets, 1):
                type_key = "scene"
                replacement_reason = "Package reference evidence is missing."

            if type_key == "detail":
                if requested_type == "detail":
                    native_detail_capacity -= 1
                else:
                    reserved_detail_capacity -= 1
            occurrence = type_occurrences[type_key]
            type_occurrences[type_key] += 1
            theme, scene, shot, composition = _variation_for(type_key, occurrence)
            references = _safe_reference_assets(type_key, assets)
            plan_items.append(
                {
                    "id": f"plan-{len(plan_items) + 1:02d}",
                    "order": len(plan_items) + 1,
                    "type_key": type_key,
                    "title": _TYPE_TITLES[type_key],
                    "reference_asset_ids": references,
                    "theme": theme,
                    "scene": scene,
                    "shot": shot,
                    "composition": composition,
                    "copy_enabled": False,
                    "copy_text": "",
                    "replacement_reason": replacement_reason,
                    "warnings": [replacement_reason] if replacement_reason else [],
                    "final_prompt": "",
                }
            )
    return {
        "target_count": target_count,
        "assets": [dict(asset) for asset in assets],
        "plan_items": plan_items,
        "used_ai_plan": False,
    }


def _ai_plan_items(ai_plan):
    if isinstance(ai_plan, list):
        return ai_plan
    if not isinstance(ai_plan, Mapping):
        return None
    for key in ("plan_items", "items"):
        if isinstance(ai_plan.get(key), list):
            return ai_plan[key]
    return None


def _variation_signature(value):
    return "".join(character.casefold() for character in value if character.isalnum())


def _validated_ai_plan(deterministic_plan, assets, ai_plan):
    candidates = _ai_plan_items(ai_plan)
    planned_items = deterministic_plan["plan_items"]
    if not isinstance(candidates, list) or len(candidates) != len(planned_items):
        return None

    asset_ids = {asset["id"] for asset in assets}
    normalized_items = []
    seen_values = {type_key: {field: set() for field in ("theme", "scene", "shot", "composition")} for type_key in TYPE_KEYS}
    for planned_item, candidate in zip(planned_items, candidates):
        if not isinstance(candidate, Mapping) or candidate.get("type_key") != planned_item["type_key"]:
            return None
        references = candidate.get("reference_asset_ids")
        if (
            not isinstance(references, list)
            or not 1 <= len(references) <= 3
            or any(not isinstance(asset_id, str) or asset_id not in asset_ids for asset_id in references)
            or len(set(references)) != len(references)
        ):
            return None
        allowed_references = set(select_reference_assets(planned_item["type_key"], assets, 3))
        if not set(references).issubset(allowed_references):
            return None
        scene = _clean_text(candidate.get("scene"))
        composition = _clean_text(candidate.get("composition"))
        if not scene or not composition:
            return None

        item = dict(planned_item)
        item["reference_asset_ids"] = references
        item["scene"] = scene
        item["composition"] = composition
        for field in ("theme", "shot"):
            value = _clean_text(candidate.get(field))
            if value:
                item[field] = value
        for field in ("theme", "scene", "shot", "composition"):
            signature = _variation_signature(item[field])
            if not signature or signature in seen_values[item["type_key"]][field]:
                return None
            seen_values[item["type_key"]][field].add(signature)
        normalized_items.append(item)
    return normalized_items


def _validated_plan_assets(draft):
    errors = validate_suite_draft(draft)
    if errors:
        raise ValueError("Invalid suite draft: " + "; ".join(errors))

    raw_assets = draft["assets"]
    if any(
        not isinstance(asset, Mapping)
        or not (_clean_text(asset.get("id")) or _clean_text(asset.get("path") or asset.get("file_path")))
        for asset in raw_assets
    ):
        raise ValueError("assets must contain resolvable reference image mappings")
    return normalize_assets(raw_assets)


def plan_suite(draft, ai_plan=None):
    """Build a safe suite plan, accepting AI detail only after full validation."""
    assets = _validated_plan_assets(draft)
    deterministic_plan = _build_deterministic_plan(draft, assets)
    if any(not 1 <= len(item["reference_asset_ids"]) <= 3 for item in deterministic_plan["plan_items"]):
        raise ValueError("assets must provide one to three relevant references for every plan item")
    ai_items = _validated_ai_plan(deterministic_plan, assets, ai_plan)
    if ai_items is None:
        return deterministic_plan
    return {
        "target_count": deterministic_plan["target_count"],
        "assets": deterministic_plan["assets"],
        "plan_items": ai_items,
        "used_ai_plan": True,
    }


def _validate_target_count(target_count):
    if isinstance(target_count, bool) or not isinstance(target_count, int):
        raise ValueError("target_count must be an integer between 1 and 10")
    if not 1 <= target_count <= TEMU_STANDARD_PROFILE["max_count"]:
        raise ValueError("target_count must be between 1 and 10")


def _empty_type_counts():
    return {type_key: 0 for type_key in TYPE_KEYS}


def build_default_type_counts(target_count=8):
    """Return a fresh, valid default type mix for one to ten images."""
    _validate_target_count(target_count)
    counts = _empty_type_counts()
    remaining = target_count

    for type_key, count in DEFAULT_TYPE_COUNTS.items():
        assigned = min(count, remaining)
        counts[type_key] = assigned
        remaining -= assigned
        if not remaining:
            return counts

    for type_key in ("selling-point", "scene", "detail", "package", "compare", "steps"):
        if not remaining:
            break
        counts[type_key] += 1
        remaining -= 1
    return counts


def _coerce_count(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def normalize_type_counts(type_counts, target_count):
    """Return known, non-negative type counts whose total is target_count."""
    _validate_target_count(target_count)
    source = type_counts if isinstance(type_counts, Mapping) else {}
    counts = {type_key: _coerce_count(source.get(type_key, 0)) for type_key in TYPE_KEYS}

    excess = sum(counts.values()) - target_count
    if excess > 0:
        for type_key in reversed(TYPE_KEYS):
            reduction = min(counts[type_key], excess)
            counts[type_key] -= reduction
            excess -= reduction
            if not excess:
                return counts

    missing = target_count - sum(counts.values())
    if missing:
        defaults = build_default_type_counts(target_count)
        for type_key in TYPE_KEYS:
            desired = defaults[type_key]
            increment = min(desired if counts[type_key] == 0 else 0, missing)
            counts[type_key] += increment
            missing -= increment
            if not missing:
                return counts
        for type_key in ("selling-point", "scene", "detail", "package", "compare", "steps"):
            if not missing:
                break
            counts[type_key] += 1
            missing -= 1
    return counts


def validate_suite_draft(draft):
    """Return human-readable errors for a suite draft, or an empty list if valid."""
    if not isinstance(draft, Mapping):
        return ["draft must be a mapping"]

    errors = []
    target_count = draft.get("target_count")
    target_is_valid = isinstance(target_count, int) and not isinstance(target_count, bool) and 1 <= target_count <= 10
    if not target_is_valid:
        errors.append("target_count must be between 1 and 10")

    assets = draft.get("assets")
    if not isinstance(assets, list) or not 1 <= len(assets) <= 14:
        errors.append("assets must contain between 1 and 14 reference images")

    type_counts = draft.get("selected_type_counts")
    if not isinstance(type_counts, Mapping):
        errors.append("selected_type_counts must be a mapping")
        return errors

    unknown_type_keys = set(type_counts) - set(TYPE_KEYS)
    if unknown_type_keys:
        errors.append("selected_type_counts contains unknown image types")
    if any(_coerce_count(count) != count for count in type_counts.values()):
        errors.append("selected_type_counts must contain non-negative integer counts")
    if target_is_valid and sum(_coerce_count(type_counts.get(type_key, 0)) for type_key in TYPE_KEYS) != target_count:
        errors.append("selected_type_counts must sum to target_count")
    elif not target_is_valid:
        errors.append("selected_type_counts must sum to target_count")
    return errors
