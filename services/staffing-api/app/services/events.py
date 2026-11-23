from __future__ import annotations

from app.staffing_store import StaffingStore, month_key_to_int
from app.state_machine import TERMINAL_STATES, can_transition


def _release_candidates(store: StaffingStore, candidates) -> int:
    n = 0
    for c in candidates:
        if c.status in TERMINAL_STATES or not can_transition(c.status, "release"):
            continue
        store.update_candidate_status(c.id, "Released")
        store.set_candidate_reservations_status(c.id, "Released")
        n += 1
    return n


def handle_project_event(store: StaffingStore, event: dict, ports) -> dict:
    event_type = event.get("type")
    project_id = event.get("project_id")
    payload = event.get("payload") or {}
    released = 0
    if event_type in {"project_cancelled", "demand_cancelled"}:
        released = store.release_demand(project_id)
        ports.notifications.notify("stakeholders", f"Project event {event_type}", event)
    elif event_type == "dates_changed":
        start, end = payload.get("start_date"), payload.get("end_date")
        if start and end:
            lo, hi = month_key_to_int(start), month_key_to_int(end)
            stale = [
                c
                for c in store.list_candidates(project_id=project_id)
                if any(not lo <= month_key_to_int(m.month_key) <= hi for m in c.months)
            ]
            released = _release_candidates(store, stale)
            if released:
                ports.notifications.notify("lead", "Allocations outside new project dates were released", event)
    store.insert_audit("project-track", event_type or "event", "project", str(project_id), {"released": released, **payload})
    store.insert_outbox("project_event", {"type": event_type, "project_id": project_id})
    ports.pt_events.publish(event)
    return {"handled": True, "released_candidates": released}
