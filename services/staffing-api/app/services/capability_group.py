"""Primary + secondary capability pairing for Project Track resource sections.

Selections whose launch filters share the same primary and secondary capability belong to one
section. Other filters (department, location, country, grade) never affect the key.
"""

from __future__ import annotations

from typing import Any


def _first(filters: dict[str, Any], key: str) -> str:
    raw = filters.get(key)
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    return str(raw or "").strip().casefold()


def capability_group_key_from_filters(filters: dict[str, Any] | None) -> str:
    filters = filters or {}
    return f"{_first(filters, 'primary_capability')}|{_first(filters, 'secondary_capability')}"
