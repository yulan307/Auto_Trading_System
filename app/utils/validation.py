from __future__ import annotations


def ensure_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def ensure_numeric(value, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric.")
    return float(value)


def ensure_positive_or_none(value, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = ensure_numeric(value, field_name)
    if numeric <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return numeric
