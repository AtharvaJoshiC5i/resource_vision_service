"""Workflow payload carries each selection's capability section (synthetic data only)."""

from app.services.capability_group import capability_group_key_from_filters as key

START, END = "2026-12-01", "2027-06-30"


def test_key_uses_primary_and_secondary_only():
    a = {"primary_capability": [" Pharma CI "], "secondary_capability": ["Oncology"], "location": ["Pune"]}
    b = {"primary_capability": ["pharma ci"], "secondary_capability": ["ONCOLOGY"], "grade": ["G5"]}
    assert key(a) == key(b) == "pharma ci|oncology"
    assert key({"primary_capability": ["Pharma CI"], "secondary_capability": ["NLP"]}) != key(a)
    assert key({}) == key(None) == "|"
    assert key({"primary_capability": "Pharma CI"}) == "pharma ci|"


def _select(client, token, employee, filters, skills=()):
    demand = client.post("/api/staffing/demands", json={
        "project_id": "P-SEC", "position_id": "Pharma CI / Oncology", "start_date": START, "end_date": END,
        "filters": filters, "required_skills": list(skills), "launch_token": token,
    })
    assert demand.status_code == 200, demand.text
    cand = client.post("/api/staffing/candidates", json={
        "demand_id": demand.json()["demand_id"], "employee_key": employee, "launch_token": token,
    })
    assert cand.status_code == 200, cand.text


def test_workflow_candidates_carry_section_key_filters_and_skills(client, token, emp):
    pune = {"primary_capability": ["Pharma CI"], "secondary_capability": ["Oncology"], "location": ["Pune"]}
    gurgaon = {"primary_capability": ["pharma ci"], "secondary_capability": ["oncology"], "location": ["Gurgaon"]}
    other = {"primary_capability": ["Pharma CI"], "secondary_capability": ["Immunology"]}
    _select(client, token, emp[0], pune, [{"name": "SQL", "level": "Applied"}])
    _select(client, token, emp[1], gurgaon)
    _select(client, token, emp[2], other)

    body = client.get("/api/staffing/projects/P-SEC/workflow").json()
    by_emp = {c["employee_key"]: c for c in body["candidates"]}
    a, b, c = by_emp[emp[0]], by_emp[emp[1]], by_emp[emp[2]]
    assert a["capability_group_key"] == b["capability_group_key"] == "pharma ci|oncology"
    assert c["capability_group_key"] == "pharma ci|immunology"
    assert a["demand_filters"] == pune and b["demand_filters"]["location"] == ["Gurgaon"]
    assert a["required_skills"] == [{"name": "SQL", "level": "Applied"}]
    assert b["required_skills"] == []
