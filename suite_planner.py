"""Pure domain rules for ecommerce standard image suites."""

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
