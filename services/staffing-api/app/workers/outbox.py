"""Debounced outbox publisher.

Reservation, release and PT events are queued in ``dbo.rv_staffing_Outbox``. Publishing
invalidates the availability caches so the next read picks up the new reservations, and is
where a real ``dbo.rv2_Refresh`` call would be wired once Project Track signs off (D9).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from app.config import get_settings
from app.staffing_store import StaffingStore, utcnow

logger = logging.getLogger("staffing.outbox")


def _invalidate_caches(ports) -> None:
    from app.rv import service as rv_service

    rv_service._state["checked"] = 0.0  # noqa: SLF001 — force version re-check
    try:
        ports.skills.refresh()
    except Exception:  # noqa: BLE001
        logger.exception("Skills refresh failed")


def publish_pending(store: StaffingStore, ports, *, force: bool = False) -> dict:
    """Publish queued events. Without ``force`` waits ``REFRESH_DEBOUNCE_SECONDS`` after the newest event."""
    pending = store.list_pending_outbox()
    if not pending:
        return {"published": 0, "pending": 0}
    settings = get_settings()
    newest = max(p.created_at for p in pending)
    if not force and utcnow() - newest < timedelta(seconds=settings.refresh_debounce_seconds):
        return {"published": 0, "pending": len(pending), "debounced": True}
    for row in pending:
        logger.info("outbox publish %s %s", row.event_type, row.payload)
    _invalidate_caches(ports)
    store.mark_outbox_published([p.id for p in pending])
    return {"published": len(pending), "pending": 0}
