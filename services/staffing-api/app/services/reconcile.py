from __future__ import annotations

from app.staffing_store import StaffingStore


def reconcile(store: StaffingStore, ports) -> dict:
    """Compare reservations with rows written to Project Track.

    * Confirmed reservation with no PT row  -> ``missing_pt_row``
    * Reserved reservation (PT write never completed) -> ``pending_pt_write``
    """
    mismatches = []
    written_keys = {w.get("idempotency_key") for w in ports.written_rows}
    for res in store.list_reservations():
        if res.status == "Confirmed" and res.idempotency_key not in written_keys:
            issue = "missing_pt_row"
        elif res.status == "Reserved":
            issue = "pending_pt_write"
        else:
            continue
        mismatches.append(
            {"reservation_id": res.id, "idempotency_key": res.idempotency_key, "issue": issue}
        )
    return {"ok": not mismatches, "mismatches": mismatches}
