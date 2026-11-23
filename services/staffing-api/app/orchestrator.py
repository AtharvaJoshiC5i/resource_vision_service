from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from rv_availability import engine as eng

from app.database import DatabaseError
from app.services.final_check import final_check
from app.services.kb_training_payload import build_kb_training_payload, next_kb_request_id
from app.staffing_store import (
    CandidateRow,
    DemandRow,
    KbRequestRow,
    ReservationRow,
    StaffingStore,
    month_key_to_int,
    normalize_month_key,
    utcnow,
)
from app.state_machine import can_transition, transition
from app.locks import lock_for_employee
from app.services.employee_blocks import on_employee_confirmed, release_block_for_candidate
from app.services.mnh_email import build_staffing_email
from app.training_split import split_training_buffer


def _fail(reason: str, **extra) -> dict:
    return {"ok": False, "reason": reason, **extra}


def _move(store: StaffingStore, candidate: CandidateRow, event: str) -> None:
    """Apply one state-machine event and persist it."""
    candidate.status = transition(candidate.status, event)
    store.update_candidate_status(candidate.id, candidate.status)


# ---------------------------------------------------------------------------
# Demand / candidate setup
# ---------------------------------------------------------------------------


def validate_demand_window(start_date: str, end_date: str) -> None:
    try:
        start, end = date.fromisoformat(start_date[:10]), date.fromisoformat(end_date[:10])
    except ValueError as exc:
        raise ValueError("start_date and end_date must be ISO dates (YYYY-MM-DD)") from exc
    if end < start:
        raise ValueError("end_date must not be before start_date")


def create_candidate(store: StaffingStore, demand_id: str, employee_key: str) -> CandidateRow:
    """Low-level insert only; prefer create_candidate_with_block from employee_blocks for API flows."""
    return store.create_candidate(demand_id, employee_key)


def set_candidate_hours(
    store: StaffingStore,
    candidate: CandidateRow,
    demand: DemandRow,
    months: list[dict],
    *,
    allow_window_extend: bool = False,
) -> CandidateRow:
    """Validate hours against capacity and the demand window (D21), then persist."""
    if candidate.status in ("Reserved", "Confirmed", "Released"):
        raise ValueError(f"Hours cannot change while the candidate is {candidate.status}")
    if not months:
        raise ValueError("At least one month of hours is required")
    lo, hi = month_key_to_int(demand.start_date), month_key_to_int(demand.end_date)
    seen: dict[str, float] = {}
    for m in months:
        key = normalize_month_key(m["month_key"])
        hours = float(m["hours"])
        if hours <= 0:
            raise ValueError(f"Hours for {key[:7]} must be greater than zero")
        if hours > eng.CAPACITY_HOURS:
            raise ValueError(f"Hours for {key[:7]} exceed monthly capacity of {eng.CAPACITY_HOURS:.0f} h")
        if not allow_window_extend and not lo <= month_key_to_int(key) <= hi:
            raise ValueError(
                f"{key[:7]} is outside the project window {demand.start_date[:7]} → {demand.end_date[:7]}"
            )
        seen[key] = hours
    return store.set_candidate_hours(candidate.id, [{"month_key": k, "hours": h} for k, h in sorted(seen.items())])


# ---------------------------------------------------------------------------
# Selection paths
# ---------------------------------------------------------------------------


def action_direct(store: StaffingStore, candidate: CandidateRow, ports) -> dict:
    if candidate.status == "Skills Matched":
        return {"ok": True, "status": candidate.status}
    if not can_transition(candidate.status, "direct_select"):
        return _fail(f"Direct select is not allowed from {candidate.status}")
    check = final_check(store, candidate, ports)
    if not check.get("ok"):
        return {"ok": False, **check}
    _move(store, candidate, "direct_select")
    return {"ok": True, "status": candidate.status}


def _kb_training_window(demand: DemandRow, training_ratio: float) -> tuple[int, int]:
    start = date.fromisoformat(demand.start_date[:10])
    days = max(0, (start - utcnow().date()).days)
    return split_training_buffer(days, training_ratio)


def action_kb(
    store: StaffingStore,
    candidate: CandidateRow,
    demand: DemandRow,
    ports,
    training_ratio: float,
    skill_levels: tuple[str, ...],
) -> dict:
    return action_kb_batch(store, demand, [candidate], ports, training_ratio, skill_levels)


def action_kb_batch(
    store: StaffingStore,
    demand: DemandRow,
    candidates: list[CandidateRow],
    ports,
    training_ratio: float,
    skill_levels: tuple[str, ...],
) -> dict:
    if not candidates:
        return _fail("At least one candidate is required for Knowledge Benchmarking")

    for candidate in candidates:
        retry = candidate.status == "KB Pending"
        if not retry and not can_transition(candidate.status, "send_kb"):
            return _fail(f"Sending to Knowledge Benchmarking is not allowed from {candidate.status}")
        check = final_check(store, candidate, ports)
        if not check.get("ok"):
            return {"ok": False, **check, "candidate_id": candidate.id}

    training_days, buffer_days = _kb_training_window(demand, training_ratio)
    employee_keys = [c.employee_key for c in candidates]

    open_requests = [store.get_open_kb_request(c.id) for c in candidates]
    open_requests = [r for r in open_requests if r is not None]
    if len(candidates) == 1 and open_requests:
        ext_request_id = (open_requests[0].payload or {}).get("request_id") or next_kb_request_id(
            store, demand.project_id
        )
    else:
        ext_request_id = next_kb_request_id(store, demand.project_id)

    payload = build_kb_training_payload(
        request_id=ext_request_id,
        demand=demand,
        employee_keys=employee_keys,
        ports=ports,
        skill_levels=skill_levels,
        training_days=training_days,
        buffer_days=buffer_days,
        training_ratio=training_ratio,
    )

    for candidate in candidates:
        if candidate.status != "KB Pending":
            _move(store, candidate, "send_kb")

    kb_requests: list[tuple[CandidateRow, KbRequestRow]] = []
    for candidate in candidates:
        request = store.get_open_kb_request(candidate.id)
        if request is None:
            request = store.create_kb_request(candidate.id, training_days, buffer_days, payload, "Sent")
        else:
            store.update_kb_request(request.id, request.status, payload=payload)
            request.payload = payload
        kb_requests.append((candidate, request))

    kb_resp = ports.kb.send_training_request(payload)
    if kb_resp.get("accepted"):
        for candidate, request in kb_requests:
            _move(store, candidate, "kb_start")
            store.update_kb_request(request.id, "Training")
        single = candidates[0]
        return {
            "ok": True,
            "status": single.status if len(candidates) == 1 else "Training",
            "kb": kb_resp,
            "request_id": ext_request_id,
            "kb_request_ids": [r.id for _, r in kb_requests],
            "payload": payload,
        }

    reason = kb_resp.get("reason") or "Knowledge Benchmarking did not accept the request"
    for candidate, request in kb_requests:
        store.update_kb_request(request.id, "Rejected", reason)
        ports.notifications.notify("lead", "KB request failed; retry from the queue", {"candidate_id": candidate.id})
    single = candidates[0]
    return {
        "ok": True,
        "status": single.status if len(candidates) == 1 else "KB Pending",
        "kb": kb_resp,
        "request_id": ext_request_id,
        "kb_request_ids": [r.id for _, r in kb_requests],
        "warning": reason,
        "payload": payload,
    }


def training_outcome(store: StaffingStore, candidate: CandidateRow, success: bool, ports, reason: str | None = None) -> dict:
    if candidate.status != "Training":
        return _fail(f"Training outcome requires status Training (was {candidate.status})")
    request = store.get_open_kb_request(candidate.id)
    if success:
        _move(store, candidate, "training_success")
        if request:
            store.update_kb_request(request.id, "Completed")
        store.insert_outbox("skills_updated", {"candidate_id": candidate.id, "employee_key": candidate.employee_key})
    else:
        _move(store, candidate, "training_failed")
        if request:
            store.update_kb_request(request.id, "Failed", reason)
        ports.notifications.notify("lead", "Training failed or delayed", {"candidate_id": candidate.id})
    return {"ok": True, "status": candidate.status}


def action_interview(store: StaffingStore, candidate: CandidateRow, ports, expiry_days: int) -> dict:
    if not can_transition(candidate.status, "interview"):
        return _fail(f"Booking an interview is not allowed from {candidate.status}")
    check = final_check(store, candidate, ports)
    if not check.get("ok"):
        return {"ok": False, **check}
    _move(store, candidate, "interview")
    _move(store, candidate, "book")
    expires = utcnow() + timedelta(days=expiry_days)
    interview = store.create_interview(candidate.id, expires)
    ports.notifications.notify("lead", "Interview booked", {"candidate_id": candidate.id})
    return {"ok": True, "status": candidate.status, "interview_id": interview.id, "expires_at": expires.isoformat()}


def interview_outcome(
    store: StaffingStore,
    candidate: CandidateRow,
    outcome: str,
    ports,
    rejection_type: str | None = None,
    reason: str | None = None,
) -> dict:
    outcome = outcome.lower()
    if outcome not in {"pass", "reject"}:
        return _fail("outcome must be 'pass' or 'reject'")
    interview = store.get_active_interview(candidate.id)
    if outcome == "pass" and candidate.status == "Skills Matched":
        return {"ok": True, "status": candidate.status, "idempotent": True}
    if candidate.status != "Interview Booked":
        return _fail(f"Interview outcome requires status Interview Booked (was {candidate.status})")
    if outcome == "reject":
        if not (reason or "").strip():
            return _fail("A rejection reason is required")
        rtype = (rejection_type or "Technical").title()
        if rtype not in {"Technical", "Non-Technical", "Non-technical"}:
            return _fail("rejection_type must be Technical or Non-technical")
        _move(store, candidate, "reject")
        release_block_for_candidate(store, candidate.id, "interview_rejected")
        if interview:
            store.update_interview(interview.id, "Rejected", "reject", rtype, reason.strip())
        if rtype == "Technical":
            demand = store.get_demand(candidate.demand_id)
            payload = {
                "employee_key": candidate.employee_key,
                "reason": reason.strip(),
                "candidate_id": candidate.id,
                "project_id": demand.project_id if demand else None,
                "source": "interview_rejection",
            }
            ports.notifications.notify("kb", "Technical rejection feedback", payload)
            send_feedback = getattr(ports.kb, "send_interview_rejection_feedback", None)
            if callable(send_feedback):
                send_feedback(payload)
        return {"ok": True, "status": candidate.status}
    _move(store, candidate, "pass")
    if interview:
        store.update_interview(interview.id, "Passed", "pass")
    return {"ok": True, "status": candidate.status}


def expire_interviews(store: StaffingStore, now: datetime | None = None) -> int:
    """Move interview holds past their expiry to Expired (hold lapses; nothing was reserved)."""
    now = now or utcnow()
    expired = 0
    for iv in store.list_due_interviews(now):
        cand = store.get_candidate(iv.candidate_id)
        store.update_interview(iv.id, "Expired", "expire")
        if cand and can_transition(cand.status, "expire"):
            _move(store, cand, "expire")
            release_block_for_candidate(store, cand.id, "interview_expired")
        expired += 1
    return expired


# ---------------------------------------------------------------------------
# Reservation + Project Track write
# ---------------------------------------------------------------------------


def _write_to_pt(store: StaffingStore, cand: CandidateRow, demand: DemandRow, ports) -> list[str]:
    """Idempotently write every month to Project Track; returns failure messages."""
    problems: list[str] = []
    for cm in cand.months:
        payload = {
            "employee_id": cand.employee_key,
            "project_id": demand.project_id,
            "month_key": cm.month_key,
            "effort_value": cm.hours,
            "is_override": False,
            "proposal_number": demand.proposal_number,
            "sub_project_name": demand.sub_project_name,
        }
        try:
            result = ports.pt_write.write_allocation(payload, f"{cand.id}:{cm.month_key}")
        except Exception as exc:  # noqa: BLE001 — writer failures must not lose the reservation
            problems.append(f"{cm.month_key[:7]}: {exc}")
            continue
        if result.get("status") not in {"confirmed", "duplicate"}:
            problems.append(f"{cm.month_key[:7]}: {result.get('status', 'unknown')}")
    return problems


def run_final_check_and_reserve(
    store: StaffingStore,
    candidate: CandidateRow,
    demand: DemandRow,
    actor: str,
    ports,
) -> dict:
    """Final check → reserve → write to PT → confirm. Safe to call again after a partial failure."""
    with lock_for_employee(candidate.employee_key):
        cand = store.get_candidate(candidate.id) or candidate

        if cand.status == "Confirmed":
            reservations = [r.id for r in store.list_reservations(cand.id)]
            return {"ok": True, "reservations": reservations, "status": "Confirmed", "idempotent": True}
        if cand.status not in ("Skills Matched", "Reserved"):
            return _fail(f"Candidate must be Skills Matched before reservation (was {cand.status})")

        check = final_check(store, cand, ports)
        if not check.get("ok"):
            return {"ok": False, **check}

        try:
            if cand.status == "Skills Matched":
                _move(store, cand, "final_check_ok")
                for cm in cand.months:
                    store.insert_reservation(
                        ReservationRow(
                            id=str(uuid.uuid4()),
                            candidate_id=cand.id,
                            demand_id=demand.id,
                            employee_key=cand.employee_key,
                            month_key=cm.month_key,
                            hours=cm.hours,
                            status="Reserved",
                            idempotency_key=f"{cand.id}:{cm.month_key}",
                        )
                    )
                store.insert_audit(actor, "reserve", "candidate", cand.id, {"months": len(cand.months)})
        except DatabaseError as exc:
            # Roll the candidate back so the lead can retry once capacity is clear.
            store.set_candidate_reservations_status(cand.id, "Released")
            store.update_candidate_status(cand.id, "Skills Matched")
            return _fail(str(exc))

        problems = _write_to_pt(store, cand, demand, ports)
        if problems:
            store.insert_outbox("pt_write_retry", {"candidate_id": cand.id, "problems": problems})
            return _fail(
                "Hours are reserved but the Project Track write did not complete; retry final check.",
                status="Reserved",
                problems=problems,
            )

        store.set_candidate_reservations_status(cand.id, "Confirmed")
        _move(store, cand, "pt_confirmed")
        on_employee_confirmed(store, cand.employee_key, cand.id)
        store.insert_outbox("pt_write", {"candidate_id": cand.id, "employee_key": cand.employee_key})
        store.insert_audit(actor, "confirm", "candidate", cand.id, {"project_id": demand.project_id})
        ports.zinghr_status.emit_intent(cand.employee_key, "In Project")
        reservations = [r.id for r in store.list_reservations(cand.id)]
        return {"ok": True, "reservations": reservations, "status": "Confirmed"}


def release_candidate(store: StaffingStore, candidate: CandidateRow, actor: str, ports) -> dict:
    if not can_transition(candidate.status, "release"):
        return _fail(f"Cannot release a candidate in status {candidate.status}")
    with lock_for_employee(candidate.employee_key):
        was_active = candidate.status in ("Reserved", "Confirmed")
        _move(store, candidate, "release")
        release_block_for_candidate(store, candidate.id, "released")
        freed = store.set_candidate_reservations_status(candidate.id, "Released")
        if was_active:
            store.insert_outbox("release", {"candidate_id": candidate.id})
            ports.pt_events.publish(
                {"type": "allocation_released", "candidate_id": candidate.id, "employee_key": candidate.employee_key}
            )
        store.insert_audit(actor, "release", "candidate", candidate.id, {"reservations_released": freed})
    return {"ok": True, "status": candidate.status, "reservations_released": freed}


# ---------------------------------------------------------------------------
# MyNextHire
# ---------------------------------------------------------------------------


def request_hiring(
    store: StaffingStore,
    ports,
    project_id: str,
    capability: str,
    headcount: int,
    justification: str,
    actor: str,
    *,
    context: dict | None = None,
) -> dict:
    if headcount < 1:
        raise ValueError("headcount must be at least 1")
    email_draft = build_staffing_email(
        project_id=project_id,
        capability=capability,
        headcount=headcount,
        justification=justification,
        start_date=(context or {}).get("start_date"),
        end_date=(context or {}).get("end_date"),
        position_id=(context or {}).get("position_id"),
        filters=(context or {}).get("filters"),
        required_skills=(context or {}).get("required_skills"),
        pool_outcome=(context or {}).get("pool_outcome"),
        bu_lead_cc=(context or {}).get("bu_lead_cc"),
        project_lead_name=(context or {}).get("project_lead_name"),
        project_lead_email=(context or {}).get("project_lead_email"),
    )
    payload = {
        "project_id": project_id,
        "capability": capability,
        "headcount": headcount,
        "justification": justification,
        "email_draft": email_draft,
        **(context or {}),
    }
    email_draft["delivery_status"] = "mock_sent"
    email_draft["mock_sent_at"] = utcnow().isoformat()
    resp = ports.mnh.request_hire(payload)
    stored_payload = {
        **resp,
        "email_draft": email_draft,
        "context": context or {},
        "mock_email_sent": True,
    }
    row = store.create_hiring_request(
        project_id,
        capability,
        headcount,
        justification,
        stored_payload,
        resp.get("status", "Hiring in progress"),
    )
    position_id = (context or {}).get("position_id")
    mnh_slots = store.create_mnh_slots(row.id, project_id, position_id, capability, headcount)
    store.insert_audit(
        actor,
        "hiring_request",
        "project",
        project_id,
        {
            "capability": capability,
            "headcount": headcount,
            "mnh_slot_ids": [s.id for s in mnh_slots],
            **(context or {}),
        },
    )
    from app.staffing_store import serialize

    return {
        "ok": True,
        "id": row.id,
        "status": row.status,
        "email_draft": email_draft,
        "mnh_slots": [serialize(s) for s in mnh_slots],
    }
