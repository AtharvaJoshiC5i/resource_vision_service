from __future__ import annotations

DEFAULT_LEVEL_ORDER = ("Foundational", "Applied", "Advanced", "Expert")


def level_index(level: str | None, order: tuple[str, ...] = DEFAULT_LEVEL_ORDER) -> int | None:
    if level is None:
        return None
    normalized = level.strip().casefold()
    for i, name in enumerate(order):
        if name.casefold() == normalized:
            return i
    raise ValueError(f"Unknown skill level: {level!r}; configured order: {order}")


def is_ranked(level: str | None, order: tuple[str, ...] = DEFAULT_LEVEL_ORDER) -> bool:
    """True when the level is part of the configured order and can be compared by rank."""
    try:
        return level_index(level, order) is not None
    except ValueError:
        return False


def compare_skill(
    current: str | None,
    required: str,
    order: tuple[str, ...] = DEFAULT_LEVEL_ORDER,
) -> bool:
    """Green tick when current level >= required; missing or NULL is fail (red X).

    Levels outside the configured order (the source view may use its own vocabulary) cannot
    be ranked, so they match only when both levels are the same text.
    """
    if current is None:
        return False
    if is_ranked(current, order) and is_ranked(required, order):
        return level_index(current, order) >= level_index(required, order)  # type: ignore[operator]
    return current.strip().casefold() == required.strip().casefold()


def skill_match_ticks(
    employee_skills: dict[str, str | None],
    required: list[tuple[str, str]],
    order: tuple[str, ...] = DEFAULT_LEVEL_ORDER,
) -> list[dict]:
    ticks = []
    for name, req_level in required:
        current = employee_skills.get(name.casefold())
        if current is None:
            for k, v in employee_skills.items():
                if k.casefold() == name.casefold():
                    current = v
                    break
        matched = compare_skill(current, req_level, order) if current is not None else False
        ticks.append(
            {
                "skill": name,
                "required_level": req_level,
                "current_level": current,
                "matched": matched,
                "ranked": is_ranked(req_level, order) and (current is None or is_ranked(current, order)),
            }
        )
    return ticks