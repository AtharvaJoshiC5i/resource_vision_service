"""Load-path speed checks on synthetic data only (no database is touched)."""

import time

from app.rv import facts, service

LATENCY = 0.2  # simulated round-trip per query


def _slow_rows(*_args, **_kwargs):
    time.sleep(LATENCY)
    return []


def test_snapshot_tables_are_read_in_parallel(monkeypatch):
    monkeypatch.setattr(facts, "fetch_rows", _slow_rows)
    monkeypatch.setattr(facts, "read_meta", lambda: (time.sleep(LATENCY), {"Version": 1})[1])
    started = time.perf_counter()
    data = facts._read_all_parallel()
    elapsed = time.perf_counter() - started
    assert data["meta"] == {"Version": 1}
    # nine reads: sequential would take ~1.8 s
    assert elapsed < LATENCY * 4, elapsed


def test_due_refresh_does_not_block_the_request(client, monkeypatch):
    snap = service.get_snapshot()  # demo snapshot loaded
    calls = []

    def slow_check(today):
        calls.append(today)
        time.sleep(0.5)
        service._state["checked"] = time.monotonic()

    monkeypatch.setattr(service, "_check_and_reload", slow_check)
    service._state["checked"] = 0.0
    started = time.perf_counter()
    assert service.get_snapshot() is snap
    assert time.perf_counter() - started < 0.1
    time.sleep(0.7)
    assert calls, "refresh should have run in the background"


def test_filters_endpoint_returns_deduped_options(client):
    body = client.get("/api/staffing/filters").json()
    assert set(body["options"]) == {"capabilities", "secondary_capabilities", "departments", "locations", "countries", "grades"}
    assert body["runtime"]["synthetic"] is True
    vocab = client.get("/api/staffing/skills/vocabulary").json()
    assert vocab["skills"]["names"]
