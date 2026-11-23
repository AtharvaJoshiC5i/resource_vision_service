from __future__ import annotations

from rv_availability import engine as e
from rv_availability import skills
from rv_availability import views as v

# Project Track row → Filters (launch payload keys)
_LAUNCH_KEY_MAP: tuple[tuple[str, str], ...] = (
    ("primary_capability", "capabilities"),
    ("secondary_capability", "secondary_capabilities"),
    ("department", "departments"),
    ("country", "countries"),
    ("location", "locations"),
    ("grade", "grades"),
)


def _clean_values(raw: list[str] | None) -> set[str]:
    if not raw:
        return set()
    return {s.strip() for s in raw if s and str(s).strip()}


def filters_from_launch_payload(payload: dict | None) -> v.Filters:
    """Build dimension filters from a pools/search or PT launch `filters` object."""
    f = payload or {}
    kwargs: dict = {}
    for launch_key, filters_attr in _LAUNCH_KEY_MAP:
        kwargs[filters_attr] = _clean_values(f.get(launch_key))
    return v.Filters(**kwargs)


def canonical(value: str | None) -> str:
    """Comparison key for org attributes: the sources spell the same value several ways
    ("Pharma_CI", "Pharma CI", " pharma ci "), so underscores become spaces, runs of
    whitespace collapse and case is ignored."""
    return " ".join(str(value or "").replace("_", " ").split()).casefold()


def _field_matches(emp_value: str | None, required: set[str]) -> bool:
    if not required:
        return True
    needle = canonical(emp_value)
    if not needle:
        return False
    return needle in {canonical(r) for r in required}


def dedupe_options(values: list[str]) -> list[str]:
    """One option per canonical value. The spelling without underscores is shown; selecting it
    matches every spelling through ``_field_matches``."""
    best: dict[str, str] = {}
    for v in values:
        key = canonical(v)
        if not key:
            continue
        cur = best.get(key)
        if cur is None or ("_" in cur and "_" not in v) or (("_" in cur) == ("_" in v) and v < cur):
            best[key] = v.strip()
    return sorted(best.values(), key=str.casefold)


def employee_matches_launch_filters(snap: e.Snapshot, emp: e.Employee, f: v.Filters) -> bool:
    """AND across each non-empty launch dimension; mirrors simulate_rv_service role row matching."""
    if f.business_verticals and emp.business_vertical not in f.business_verticals:
        return False
    if f.tenures and v.tenure(snap, emp) not in f.tenures:
        return False
    if f.clients and not (set(v.employee_clients(snap, emp.key, None)) & f.clients):
        return False
    if f.divisions and not _field_matches(emp.division, f.divisions):
        return False
    if not _field_matches(emp.primary_capability, f.capabilities):
        return False
    if not _field_matches(emp.secondary_capability, f.secondary_capabilities):
        return False
    if not _field_matches(emp.department, f.departments):
        return False
    if not _field_matches(emp.country, f.countries):
        return False
    if not _field_matches(emp.grade, f.grades):
        return False
    if not _field_matches(emp.location, f.locations):
        return False
    if f.skill_codes is not None and skills.normalize_code(emp.code) not in f.skill_codes:
        return False
    if f.employee_keys is not None and emp.key not in f.employee_keys:
        return False
    return True


def launch_filters_summary(f: v.Filters) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for launch_key, filters_attr in _LAUNCH_KEY_MAP:
        vals = sorted(getattr(f, filters_attr))
        if vals:
            out[launch_key] = vals
    return out


def launch_filters_empty(f: v.Filters) -> bool:
    """True when no Project Track role row dimensions are in effect."""
    return all(not getattr(f, filters_attr) for _, filters_attr in _LAUNCH_KEY_MAP)