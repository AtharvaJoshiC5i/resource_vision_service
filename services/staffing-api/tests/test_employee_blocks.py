from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.employee_blocks import EmployeeBlockLimitError, create_candidate_with_block
START, END = "2026-12-01", "2027-06-30"
MONTHS = [{"month_key": "2026-12-01", "hours": 40}]


def _demand(store, project_id: str):
    return store.create_demand(
        project_id=project_id,
        proposal_number=None,
        sub_project_name=None,
        position_id="R1",
        start_date=START,
        end_date=END,
        filters_json={},
        required_skills_json=[],
        created_by="lead-a",
    )


def test_block_limit_and_reject_frees_slot(client: TestClient, token: str, emp: list[str]):
    key = emp[0]
    max_slots = get_settings().employee_block_max
    assert max_slots == 3

    for i in range(max_slots):
        d = _demand(get_staffing_store(), f"PR-BLOCK-{i}")
        create_candidate_with_block(
            get_staffing_store(),
            d,
            key,
            actor_id=f"manager-{i}",
            actor_display_name=f"Manager {i}",
            max_slots=max_slots,
        )

    store = get_staffing_store()
    with pytest.raises(EmployeeBlockLimitError) as err:
        d4 = _demand(store, "PR-BLOCK-4")
        create_candidate_with_block(store, d4, key, "manager-4", "Manager 4", max_slots)
    assert len(err.value.holders) == max_slots

    victims = [c for c in store.list_candidates() if c.employee_key == key.upper()]
    assert len(victims) == max_slots
    cand = victims[0]
    client.post(f"/api/staffing/candidates/{cand.id}/hours", json={"months": MONTHS})
    client.post(f"/api/staffing/candidates/{cand.id}/actions/interview", json={"launch_token": token})
    client.post(
        f"/api/staffing/candidates/{cand.id}/interview-outcome",
        json={"launch_token": token, "outcome": "reject", "rejection_type": "Non-technical", "reason": "Fit"},
    )

    active = store.list_active_blocks_for_employee(key)
    assert len(active) == max_slots - 1

    d5 = _demand(store, "PR-BLOCK-5")
    create_candidate_with_block(store, d5, key, "manager-5", "Manager 5", max_slots)
    assert len(store.list_active_blocks_for_employee(key)) == max_slots


def test_pool_shows_block_holders(client: TestClient, token: str, emp: list[str]):
    store = get_staffing_store()
    key = emp[0]
    d = _demand(store, f"PR-VIS-{key}")
    create_candidate_with_block(store, d, key, "m-1", "Lead One", 3)
    r = client.post(
        "/api/staffing/pools/search",
        json={
            "project_id": "OTHER",
            "start_date": START,
            "end_date": END,
            "launch_token": token,
            "month_hours": [{"month_key": "2026-12-01", "hours": 40}],
        },
    ).json()
    row = next(e for e in r["employees"] if e["employee_key"] == key)
    assert row["block_slots_active"] == 1
    assert row["active_blocks"][0]["actor_display_name"] == "Lead One"


from app.staffing_store import get_staffing_store  # noqa: E402