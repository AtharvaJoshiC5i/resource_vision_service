from __future__ import annotations

from rv_availability import engine as e


def bench_class(
    snap: e.Snapshot,
    emp: e.Employee,
    *,
    current_month: int | None = None,
    future_horizon_months: int = 3,
) -> str:
    """Handoff §10.2 draft bench classes."""
    month = current_month if current_month is not None else snap.window[0]
    em = snap.employee_months.get((emp.key, month))
    if em is not None:
        status = em.status
    elif emp.hr_matched and emp.dates_valid:
        status = e.FULLY_AVAILABLE
    else:
        status = e.UNVERIFIED

    if status in (e.FULLY_COMMITTED, e.OVER_ALLOCATED):
        return "In Project"
    if status == e.PARTIALLY_AVAILABLE:
        return "Partially Allocated"
    if status == e.FULLY_AVAILABLE:
        return "True Bench"

    idx = snap.window.index(month) if month in snap.window else 0
    horizon = snap.window[idx : idx + future_horizon_months]
    for m in horizon:
        future_em = snap.employee_months.get((emp.key, m))
        if future_em and future_em.remaining and future_em.remaining > 0:
            return "Future Bench"
    return "In Project"