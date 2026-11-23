from __future__ import annotations

from rv_availability.staffing.bookable_hours import bookable_hours_for_month

from app.services.snapshot import get_availability_snapshot, reserved_hours_map
from app.staffing_store import CandidateRow, StaffingStore, month_key_to_int


def final_check(store: StaffingStore, candidate: CandidateRow, ports) -> dict:
    """Re-validate bookable hours against the freshest snapshot plus all active reservations."""
    # Cheap freshness gate: re-read the rv2 version marker (reload only if it changed).
    snap = get_availability_snapshot(fresh=True)
    emp = snap.employees.get(candidate.employee_key.upper())
    if not emp:
        return {"ok": False, "reason": "Employee not found in snapshot"}
    if not candidate.months:
        return {"ok": False, "reason": "No monthly hours set for this candidate"}

    reserved = reserved_hours_map(store)
    own = {
        (r.employee_key.upper(), month_key_to_int(r.month_key)): r.hours
        for r in store.list_reservations(candidate.id)
        if r.status in ("Reserved", "Confirmed")
    }
    failures: list[str] = []
    for cm in candidate.months:
        month_int = month_key_to_int(cm.month_key)
        key = (candidate.employee_key.upper(), month_int)
        em = snap.employee_months.get(key)
        existing = reserved.get(key, 0.0) - own.get(key, 0.0)
        bookable = bookable_hours_for_month(em, emp, reserved_hours=max(0.0, existing))
        if cm.hours > bookable + 1e-6:
            failures.append(f"Over capacity in {cm.month_key[:7]} by {cm.hours - bookable:.0f} h")

    if failures:
        return {"ok": False, "reason": "; ".join(failures), "reasons": failures}

    return {"ok": True}
