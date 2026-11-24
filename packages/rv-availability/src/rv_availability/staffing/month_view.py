"""Staffing pool month cells — planning defaults when Project Track has no employee-month row."""
from __future__ import annotations

from dataclasses import dataclass

from rv_availability import engine as e
from rv_availability.staffing.bookable_hours import bookable_hours_for_month


@dataclass(frozen=True)
class StaffingMonthView:
    status: str
    remaining: float | None
    planned: float | None
    bookable_hours: float
    """``project_track`` when a row exists; ``assumed_available`` when planning default applies."""

    source: str


def staffing_month_view(
    em: e.EmployeeMonth | None,
    emp: e.Employee,
    *,
    reserved_hours: float = 0.0,
) -> StaffingMonthView:
    """
    Pools and staffing actions treat a missing PT row as fully available until real effort exists.

    When Project Track later supplies an employee-month row, status and hours follow that row.
    """
    if em is not None:
        bookable = bookable_hours_for_month(em, emp, reserved_hours=reserved_hours)
        return StaffingMonthView(
            status=em.status,
            remaining=em.remaining,
            planned=em.planned,
            bookable_hours=bookable,
            source="project_track",
        )

    bookable = bookable_hours_for_month(None, emp, reserved_hours=reserved_hours)
    if not emp.hr_matched or not emp.dates_valid:
        return StaffingMonthView(
            status=e.UNVERIFIED,
            remaining=None,
            planned=None,
            bookable_hours=bookable,
            source="assumed_available",
        )

    return StaffingMonthView(
        status=e.FULLY_AVAILABLE,
        remaining=e.CAPACITY_HOURS,
        planned=0.0,
        bookable_hours=bookable,
        source="assumed_available",
    )