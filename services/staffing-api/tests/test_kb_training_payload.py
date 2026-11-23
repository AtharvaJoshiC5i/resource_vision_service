from __future__ import annotations

from types import SimpleNamespace

from app.ports import get_ports
from app.services.kb_training_payload import build_kb_training_payload


def test_build_kb_training_payload_shape():
    ports = get_ports()
    demand = SimpleNamespace(
        project_id="SYN-PRJ-1042",
        start_date="2027-03-01",
        end_date="2027-08-31",
        required_skills_json=[
            {"name": "Python", "level": "Expert"},
            {"name": "SQL", "level": "Advanced"},
        ],
    )
    payload = build_kb_training_payload(
        request_id="RV-KB-SYN-PRJ-1042-001",
        demand=demand,
        employee_keys=["EMP001"],
        ports=ports,
        skill_levels=("Foundational", "Applied", "Advanced", "Expert"),
        training_days=85,
        buffer_days=16,
        training_ratio=0.85,
    )
    assert payload["request_type"] == "SKILL_GAP_TRAINING"
    assert payload["time_window"]["total_calendar_days"] == 101
    assert len(payload["required_skills"]) == 2
    assert payload["employee_skill_gaps"][0]["employee_id"]
    assert "gaps" in payload["employee_skill_gaps"][0]