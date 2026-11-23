from __future__ import annotations

from rv_availability import engine as e


def bookable_hours_for_month(
    em: e.EmployeeMonth | None,
    emp: e.Employee,
    *,
    no_record_bookable_capacity: float = e.CAPACITY_HOURS,
    reserved_hours: float = 0.0,
) -> float:
    """Handoff §10.1 — only Reserved/Confirmed reservations passed via reserved_hours."""
    if not emp.hr_matched or not emp.dates_valid:
        return 0.0
    if em is None:
        return max(0.0, no_record_bookable_capacity - reserved_hours)
    if em.status in (e.UNVERIFIED, e.OVER_ALLOCATED, e.FULLY_COMMITTED):
        return 0.0
    if em.status in (e.PARTIALLY_AVAILABLE, e.FULLY_AVAILABLE):
        remaining = em.remaining if em.remaining is not None else 0.0
        return max(0.0, remaining - reserved_hours)
    return 0.0