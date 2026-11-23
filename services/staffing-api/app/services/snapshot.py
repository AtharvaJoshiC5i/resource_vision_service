from __future__ import annotations

from datetime import date

from rv_availability import engine as e

from app.rv import service as rv_service
from app.staffing_store import StaffingStore


def get_availability_snapshot(*, fresh: bool = False):
    return rv_service.get_snapshot(fresh=fresh)


def reserved_hours_map(store: StaffingStore, demand_id: str | None = None) -> dict[tuple[str, int], float]:
    return store.reserved_hours_excluding_demand(demand_id)


def _month_to_int(month_key: str) -> int:
    if len(month_key) == 6 and month_key.isdigit():
        return int(month_key)
    d = date.fromisoformat(month_key[:10])
    return e.month_int(d)