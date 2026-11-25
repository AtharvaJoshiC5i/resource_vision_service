"""Snapshot loading and caching for the API.

RV_DATA_SOURCE:
  azure      (default) read the precomputed rv2_* tables; reload only when rv2_Meta.Version changes
  azure_raw  recompute from the two source tables in Python (slow; reference/oracle)
  source_tables  only the two source tables, reduced in SQL with no helper functions, views or
             precomputed tables; reload when the change fingerprint moves (see source_tables.py)
  demo       synthetic data, no database
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, datetime, timezone
from typing import Any

from app.config import get_settings
from app.database import DatabaseError, fetch_rows
from rv_availability import engine as e
from rv_availability.demo_data import build_demo

from app.rv import source_tables
from app.rv.facts import load_snapshot_from_facts, read_meta
from app.rv.sql import HR_EMPLOYEES, PROJECT_TRACK_ROWS

logger = logging.getLogger("resource_vision")
VERSION_CHECK_SECONDS = int(os.environ.get("RV_VERSION_CHECK_SECONDS", "5"))
RAW_CACHE_SECONDS = int(os.environ.get("RV_CACHE_SECONDS", "60"))
SOURCE_CHECK_SECONDS = int(os.environ.get("RV_SOURCE_CHECK_SECONDS", "60"))
SOURCE_MAX_AGE_SECONDS = int(os.environ.get("RV_SOURCE_MAX_AGE_SECONDS", "900"))

_lock = threading.Lock()
_state: dict[str, Any] = {
    "snapshot": None, "version": None, "checked": 0.0, "day": None, "meta": {},
    "fingerprint": None, "loaded": 0.0,
}


def data_source() -> str:
    if os.environ.get("RV_DATA_SOURCE"):
        return os.environ["RV_DATA_SOURCE"].strip().lower()
    return get_settings().resolved_rv_data_source()


def capacity_hours() -> float:
    return float(os.environ.get("RV_CAPACITY_HOURS", e.CAPACITY_HOURS))


def _load_raw(today: date) -> e.Snapshot:
    if data_source() == "demo":
        pt_rows, hr_rows = build_demo(today)
    else:
        pt_rows = fetch_rows(PROJECT_TRACK_ROWS)
        hr_rows = fetch_rows(HR_EMPLOYEES)
    return e.build_snapshot(pt_rows, hr_rows, today, capacity_hours())


def _reload(today: date) -> None:
    if data_source() == "azure":
        snapshot, meta = load_snapshot_from_facts()
        _state.update(snapshot=snapshot, version=int(meta["Version"]), meta={
            "version": int(meta["Version"]),
            "refreshed_utc": meta["RefreshedUtc"].isoformat() if meta["RefreshedUtc"] else None,
            "facts_date": snapshot.today.isoformat(),
            "stale": snapshot.today != today,
        })
    elif data_source() == "source_tables":
        fingerprint = source_tables.read_fingerprint()
        started = time.perf_counter()
        snapshot = source_tables.load_snapshot(today, capacity_hours())
        seconds = round(time.perf_counter() - started, 3)
        logger.info("Loaded availability from source tables in %.2fs", seconds)
        _state.update(snapshot=snapshot, version=None, fingerprint=fingerprint, meta={
            "version": None,
            "refreshed_utc": datetime.now(timezone.utc).isoformat(),
            "facts_date": today.isoformat(),
            "load_seconds": seconds,
        })
    else:
        _state.update(snapshot=_load_raw(today), version=None, meta={"version": None, "refreshed_utc": None})
    _state.update(day=today, loaded=time.monotonic())


def _check_and_reload(today: date) -> None:
    """Re-read the version marker and reload only when the data changed. Caller holds _lock."""
    try:
        if data_source() == "azure":
            meta = read_meta()
            changed = meta is None or int(meta["Version"]) != _state["version"] or _state["day"] != today
        elif data_source() == "source_tables":
            changed = (
                _state["day"] != today
                or time.monotonic() - _state["loaded"] >= SOURCE_MAX_AGE_SECONDS
                or source_tables.read_fingerprint() != _state["fingerprint"]
            )
        else:
            changed = True
        if changed or _state["snapshot"] is None:
            _reload(today)
    except DatabaseError:
        logger.exception("Resource Vision data load failed")
        if _state["snapshot"] is None:
            raise
    _state["checked"] = time.monotonic()


def _refresh_in_background(today: date) -> None:
    if not _lock.acquire(blocking=False):
        return  # a check or reload is already running

    def run() -> None:
        try:
            _check_and_reload(today)
        except Exception:  # noqa: BLE001 - the current snapshot keeps serving
            logger.exception("Background snapshot refresh failed")
        finally:
            _lock.release()

    threading.Thread(target=run, name="rv-snapshot-refresh", daemon=True).start()


def get_snapshot(*, fresh: bool = False) -> e.Snapshot:
    """Serve the snapshot without making the request wait for a refresh.

    * First load: synchronous (there is nothing to serve yet).
    * Version check due: started in the background; this request gets the current snapshot.
    * ``fresh=True`` (final check before reserving): checks the version marker now and
      reloads if it changed, so capacity is validated against the latest data.
    """
    today = date.today()
    if _state["snapshot"] is None or fresh:
        with _lock:
            if _state["snapshot"] is None or fresh:
                _check_and_reload(today)
        return _state["snapshot"]

    interval = {"azure": VERSION_CHECK_SECONDS, "source_tables": SOURCE_CHECK_SECONDS}.get(
        data_source(), RAW_CACHE_SECONDS
    )
    if time.monotonic() - _state["checked"] >= interval or _state["day"] != today:
        _refresh_in_background(today)
    return _state["snapshot"]


def warm_up() -> None:
    """Load the snapshot at startup so the first page load does not pay for it."""
    try:
        get_snapshot()
    except Exception:  # noqa: BLE001
        logger.exception("Snapshot warm-up failed; it will load on first request")


def data_info() -> dict[str, Any]:
    return dict(_state["meta"])
