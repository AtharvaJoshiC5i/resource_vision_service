import threading
from datetime import timedelta

import pytest

from app.staffing_store import get_staffing_store, utcnow
from app.training_split import split_training_buffer

START, END = "2026-12-01", "2027-06-30"
MONTHS = [{"month_key": "2026-12-01", "hours": 40}, {"month_key": "2027-01-01", "hours": 40}]


def _search(client, token, project="P1", **extra):
    body = {
        "project_id": project,
        "start_date": START,
        "end_date": END,
        "launch_token": token,
        "month_hours": MONTHS,
        **extra,
    }
    r = client.post("/api/staffing/pools/search", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _new_candidate(client, token, employee_key, project="P1", months=MONTHS):
    demand = client.post(
        "/api/staffing/demands",
        json={"project_id": project, "start_date": START, "end_date": END, "launch_token": token},
    ).json()
    cand = client.post(
        "/api/staffing/candidates",
        json={"demand_id": demand["demand_id"], "employee_key": employee_key, "launch_token": token},
    ).json()
    r = client.post(f"/api/staffing/candidates/{cand['candidate_id']}/hours", json={"months": months})
    assert r.status_code == 200, r.text
    return demand["demand_id"], cand["candidate_id"]


def _act(client, token, cid, action):
    return client.post(f"/api/staffing/candidates/{cid}/actions/{action}", json={"launch_token": token})


def _status(client, cid):
    return client.get(f"/api/staffing/candidates/{cid}").json()["status"]


@pytest.fixture
def emp(client, token):
    employees = _search(client, token)["employees"]
    assert employees, "demo data must provide a pool"
    return [e["employee_key"] for e in employees]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_85_15_split():
    for total in (0, 1, 2, 7, 10, 90):
        training, buffer = split_training_buffer(total)
        assert training + buffer == total


def test_launch_token_validation(client, token):
    ok = client.post("/api/staffing/launch/validate", json={"launch_token": token})
    assert ok.status_code == 200 and ok.json()["valid"]
    bad = client.post("/api/staffing/launch/validate", json={"launch_token": "nope"})
    assert bad.status_code == 401


def test_pools_search_shape(client, token):
    data = _search(client, token, required_skills=[{"name": "python", "level": "Applied"}])
    assert data["employees"]
    row = data["employees"][0]
    for field in (
        "interview_leads_count",
        "in_flight_status",
        "months",
        "skill_ticks",
        "block_slots_max",
        "block_slots_active",
        "block_slots_remaining",
        "can_block",
        "active_blocks",
    ):
        assert field in row


def test_unconfirmed_project_rejected(client, token):
    r = client.post(
        "/api/staffing/demands",
        json={"project_id": "P", "start_date": START, "end_date": END, "launch_token": token, "project_status": "proposed"},
    )
    assert r.status_code == 409


def test_invalid_window_rejected(client, token):
    r = client.post(
        "/api/staffing/demands",
        json={"project_id": "P", "start_date": END, "end_date": START, "launch_token": token},
    )
    assert r.status_code == 400


def test_hours_outside_window_refused(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    r = client.post(f"/api/staffing/candidates/{cid}/hours", json={"months": [{"month_key": "2026-11-01", "hours": 20}]})
    assert r.status_code == 400
    assert "outside the project window" in r.json()["detail"]
    r = client.post(f"/api/staffing/candidates/{cid}/hours", json={"months": [{"month_key": "2026-12-01", "hours": 0}]})
    assert r.status_code == 400


def test_direct_select_reserves_and_confirms(client, token, emp):
    demand_id, cid = _new_candidate(client, token, emp[0])
    assert _act(client, token, cid, "direct").status_code == 200
    assert _status(client, cid) == "Skills Matched"
    final = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "Confirmed"
    assert _status(client, cid) == "Confirmed"

    reservations = get_staffing_store().list_reservations(cid)
    assert len(reservations) == 2 and all(r.status == "Confirmed" for r in reservations)
    assert len(client.get("/api/staffing/admin/pt-writes").json()["rows"]) == 2
    assert client.post("/api/staffing/admin/reconcile").json()["ok"] is True

    # idempotent: second final-check does not duplicate PT rows
    again = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert again.status_code == 200 and again.json().get("idempotent")
    assert len(client.get("/api/staffing/admin/pt-writes").json()["rows"]) == 2

    detail = client.get(f"/api/staffing/demands/{demand_id}").json()
    assert detail["candidates"][0]["status"] == "Confirmed"


def test_confirmed_hours_reduce_bookable(client, token, emp):
    key = emp[0]
    before = {e["employee_key"]: e for e in _search(client, token)["employees"]}[key]["months"][0]["bookable_hours"]
    _, cid = _new_candidate(client, token, key, months=[{"month_key": "2026-12-01", "hours": 60}])
    _act(client, token, cid, "direct")
    client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    after = {e["employee_key"]: e for e in _search(client, token, project="P9")["employees"]}[key]["months"][0]["bookable_hours"]
    assert after == before - 60


def test_over_capacity_blocked(client, token, emp):
    key = emp[0]
    _, first = _new_candidate(client, token, key, months=[{"month_key": "2026-12-01", "hours": 150}])
    _act(client, token, first, "direct")
    assert client.post(f"/api/staffing/candidates/{first}/final-check", json={"launch_token": token}).status_code == 200
    _, second = _new_candidate(client, token, key, project="P2", months=[{"month_key": "2026-12-01", "hours": 150}])
    r = _act(client, token, second, "direct")
    assert r.status_code == 409
    assert "Over capacity" in r.json()["detail"]["reason"]


def test_interview_pass_flow(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    r = _act(client, token, cid, "interview")
    assert r.status_code == 200 and r.json()["status"] == "Interview Booked"
    assert _search(client, token)["employees"][0]["interview_leads_count"] >= 1

    # interview holds do not reduce bookable hours (D5)
    ok = client.post(
        f"/api/staffing/candidates/{cid}/interview-outcome", json={"launch_token": token, "outcome": "pass"}
    )
    assert ok.status_code == 200 and ok.json()["status"] == "Skills Matched"
    final = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert final.status_code == 200


def test_kb_training_then_interview_then_select(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0], months=[{"month_key": "2026-12-01", "hours": 40}])
    assert _act(client, token, cid, "kb").json()["status"] == "Training"
    assert (
        client.post(
            f"/api/staffing/candidates/{cid}/training-outcome", json={"launch_token": token, "outcome": "success"}
        ).json()["status"]
        == "Skills Matched"
    )
    assert _act(client, token, cid, "interview").status_code == 200
    assert _status(client, cid) == "Interview Booked"
    assert (
        client.post(
            f"/api/staffing/candidates/{cid}/interview-outcome", json={"launch_token": token, "outcome": "pass"}
        ).json()["status"]
        == "Skills Matched"
    )
    fin = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert fin.status_code == 200 and fin.json()["status"] == "Confirmed"


def test_interview_reject_requires_reason_and_is_recorded(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0], project="PR")
    _act(client, token, cid, "interview")
    bad = client.post(
        f"/api/staffing/candidates/{cid}/interview-outcome", json={"launch_token": token, "outcome": "reject"}
    )
    assert bad.status_code == 409
    ok = client.post(
        f"/api/staffing/candidates/{cid}/interview-outcome",
        json={"launch_token": token, "outcome": "reject", "rejection_type": "Technical", "reason": "Weak SQL"},
    )
    assert ok.status_code == 200 and _status(client, cid) == "Rejected"
    ivs = client.get("/api/staffing/interviews", params={"project_id": "PR"}).json()["interviews"]
    assert ivs[0]["status"] == "Rejected" and ivs[0]["rejection_reason"] == "Weak SQL"
    keys = {e["employee_key"] for e in _search(client, token, project="PR")["employees"]}
    assert emp[0] not in keys


def test_interview_expires(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    _act(client, token, cid, "interview")
    for iv in get_staffing_store().interviews.values():
        iv.expires_at = utcnow() - timedelta(minutes=1)
    assert client.post("/api/staffing/admin/expire-interviews").json()["expired"] == 1
    assert _status(client, cid) == "Expired"
    # an expired candidate can be re-booked
    assert _act(client, token, cid, "interview").status_code == 200


def test_kb_training_flow(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    r = _act(client, token, cid, "kb")
    assert r.status_code == 200 and r.json()["status"] == "Training"
    body = r.json()
    payload = body.get("payload") or {}
    assert payload.get("request_type") == "SKILL_GAP_TRAINING"
    assert payload.get("selected_employee_count") == 1
    assert "employee_skill_gaps" in payload and "skill_gap_summary" in payload
    assert body.get("request_id", "").startswith("RV-KB-")
    queue = client.get("/api/staffing/kb/requests").json()["requests"]
    assert queue[0]["status"] == "Training"
    assert queue[0]["payload"]["request_type"] == "SKILL_GAP_TRAINING"

    done = client.post(
        f"/api/staffing/candidates/{cid}/training-outcome", json={"launch_token": token, "outcome": "success"}
    )
    assert done.status_code == 200 and done.json()["status"] == "Skills Matched"
    assert client.get("/api/staffing/kb/requests").json()["requests"][0]["status"] == "Completed"
    assert client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token}).status_code == 200


def test_kb_failure_and_retry(client, token, emp):
    from app.ports import get_ports

    ports = get_ports()
    ports.kb_force_failure = True
    _, cid = _new_candidate(client, token, emp[0])
    r = _act(client, token, cid, "kb")
    assert r.status_code == 200 and r.json().get("warning")
    assert _status(client, cid) == "KB Pending"
    ports.kb_force_failure = False
    assert _act(client, token, cid, "kb").json()["status"] == "Training"

    failed = client.post(
        f"/api/staffing/candidates/{cid}/training-outcome", json={"launch_token": token, "outcome": "failed"}
    )
    assert failed.status_code == 200 and _status(client, cid) == "Training Failed/Delayed"


def test_release_frees_hours(client, token, emp):
    key = emp[0]
    _, cid = _new_candidate(client, token, key, months=[{"month_key": "2026-12-01", "hours": 100}])
    _act(client, token, cid, "direct")
    client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    rel = client.post(f"/api/staffing/candidates/{cid}/release", json={"launch_token": token})
    assert rel.status_code == 200 and rel.json()["reservations_released"] == 1
    assert _status(client, cid) == "Released"
    assert client.post(f"/api/staffing/candidates/{cid}/release", json={"launch_token": token}).status_code == 409


def test_invalid_transition_returns_conflict(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    r = client.post(
        f"/api/staffing/candidates/{cid}/training-outcome", json={"launch_token": token, "outcome": "success"}
    )
    assert r.status_code == 409
    assert (
        client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token}).status_code == 409
    )


def test_pt_writer_failure_leaves_reserved_then_retries(client, token, emp):
    from app.ports import get_ports

    ports = get_ports()
    real = ports.pt_write.write_allocation
    ports.pt_write.write_allocation = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("PT down"))
    _, cid = _new_candidate(client, token, emp[0])
    _act(client, token, cid, "direct")
    r = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert r.status_code == 409 and r.json()["detail"]["status"] == "Reserved"
    assert _status(client, cid) == "Reserved"
    assert client.post("/api/staffing/admin/reconcile").json()["mismatches"][0]["issue"] == "pending_pt_write"

    ports.pt_write.write_allocation = real
    retry = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert retry.status_code == 200 and _status(client, cid) == "Confirmed"
    assert len(client.get("/api/staffing/admin/pt-writes").json()["rows"]) == 2


def test_concurrent_reservation_cannot_overbook(client, token, emp):
    key = emp[0]
    results: list[int] = []

    def flow(project):
        _, cid = _new_candidate(client, token, key, project=project, months=[{"month_key": "2026-12-01", "hours": 150}])
        direct = _act(client, token, cid, "direct")
        if direct.status_code != 200:
            results.append(direct.status_code)
            return
        final = client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
        results.append(final.status_code)

    threads = [threading.Thread(target=flow, args=(f"PC{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) in ([200, 409], [409, 409]) or results.count(200) <= 1
    total = sum(h for (k, m), h in get_staffing_store().reserved_hours_excluding_demand(None).items() if k == key.upper())
    assert total <= 176


def test_project_cancel_releases_everything(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0], project="PX")
    _act(client, token, cid, "direct")
    client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    r = client.post("/api/staffing/events/project-track", json={"type": "project_cancelled", "project_id": "PX"})
    assert r.json()["released_candidates"] == 1
    assert _status(client, cid) == "Released"
    assert all(x.status == "Released" for x in get_staffing_store().list_reservations(cid))


def test_dates_changed_releases_out_of_window_candidates(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0], project="PD")
    _act(client, token, cid, "direct")
    r = client.post(
        "/api/staffing/events/project-track",
        json={"type": "dates_changed", "project_id": "PD", "payload": {"start_date": "2027-03-01", "end_date": "2027-06-30"}},
    )
    assert r.json()["released_candidates"] == 1
    assert _status(client, cid) == "Released"


def test_hiring_request_and_audit(client, token):
    r = client.post(
        "/api/staffing/hiring-requests",
        json={
            "launch_token": token,
            "project_id": "PH",
            "capability": "Data Engineering",
            "headcount": 2,
            "position_id": "role-1",
            "start_date": "2026-12-01",
            "end_date": "2027-06-30",
            "filters": {"primary_capability": ["Data Engineering"]},
            "required_skills": [{"name": "Python", "level": "Advanced"}],
            "source": "resource_vision_empty_pool",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email_draft"]["to"]
    assert "Staffing request" in body["email_draft"]["subject"]
    assert len(body["mnh_slots"]) == 2
    assert body["mnh_slots"][0]["status"] == "Hiring from MNH"
    rows = client.get("/api/staffing/hiring-requests", params={"project_id": "PH"}).json()["requests"]
    assert rows[0]["headcount"] == 2
    nested = rows[0].get("payload", {}).get("payload", rows[0].get("payload", {}))
    assert nested.get("position_id") == "role-1"
    assert nested.get("source") == "resource_vision_empty_pool"
    assert nested.get("email_draft", {}).get("body_text")
    prev = client.post(
        "/api/staffing/hiring-requests/preview-email",
        json={
            "launch_token": token,
            "project_id": "PH",
            "capability": "Data Engineering",
            "headcount": 1,
            "justification": "test",
        },
    )
    assert prev.status_code == 200 and "Dear HR" in prev.json()["email_draft"]["body_text"]
    bad = client.post(
        "/api/staffing/hiring-requests",
        json={"launch_token": token, "project_id": "PH", "capability": "x", "headcount": 0},
    )
    assert bad.status_code == 400
    actions = [e["action"] for e in client.get("/api/staffing/audit").json()["events"]]
    assert "hiring_request" in actions


def test_outbox_publish(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0])
    _act(client, token, cid, "direct")
    client.post(f"/api/staffing/candidates/{cid}/final-check", json={"launch_token": token})
    assert get_staffing_store().list_pending_outbox()
    out = client.post("/api/staffing/admin/outbox/publish").json()
    assert out["published"] >= 1
    assert not get_staffing_store().list_pending_outbox()


def test_pool_lists_skills_as_stored_and_meta_exposes_vocabulary(client, token):
    meta = client.get("/api/staffing/meta").json()["skills"]
    assert "Python" in meta["names"] and "Practitioner" in meta["unranked_levels"]
    assert meta["levels"][:4] == ["Foundational", "Applied", "Advanced", "Expert"]
    rows = _search(client, token, required_skills=[{"name": "Python", "level": "Practitioner"}])["employees"]
    listed = [s for r in rows for s in r["skills"]]
    assert listed and all({"name", "level"} == set(s) for s in listed)
    assert {s["level"] for s in listed} <= set(meta["levels"]) | {"Not documented"}


def test_project_workflow_bundle(client, token, emp):
    _, cid = _new_candidate(client, token, emp[0], project="PW")
    body = client.get("/api/staffing/projects/PW/workflow").json()
    assert set(body) == {"candidates", "interviews", "kb_requests", "hiring_requests", "mnh_slots"}
    assert body["candidates"][0]["id"] == cid
