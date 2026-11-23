from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Protocol

from app.config import get_settings
from app.database import DatabaseError, connect, fetch_rows

ACTIVE_RESERVATION = ("Reserved", "Confirmed")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uuid() -> str:
    return str(uuid.uuid4())


def normalize_month_key(month_key: str | int | date) -> str:
    """Canonical month key is the first day of the month as ISO text (YYYY-MM-01)."""
    if isinstance(month_key, date):
        return f"{month_key.year:04d}-{month_key.month:02d}-01"
    text = str(month_key).strip()
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:]}-01"
    d = date.fromisoformat(text[:10])
    return f"{d.year:04d}-{d.month:02d}-01"


def month_key_to_int(month_key: str | int | date) -> int:
    d = date.fromisoformat(normalize_month_key(month_key))
    return d.year * 100 + d.month


@dataclass
class DemandRow:
    id: str
    project_id: str
    proposal_number: str | None
    sub_project_name: str | None
    position_id: str | None
    start_date: str
    end_date: str
    filters_json: dict
    required_skills_json: list
    status: str
    created_by: str
    candidates: list["CandidateRow"] = field(default_factory=list)


@dataclass
class CandidateMonthRow:
    month_key: str
    hours: float


@dataclass
class CandidateRow:
    id: str
    demand_id: str
    employee_key: str
    status: str
    months: list[CandidateMonthRow] = field(default_factory=list)


@dataclass
class ReservationRow:
    id: str
    candidate_id: str
    demand_id: str
    employee_key: str
    month_key: str
    hours: float
    status: str
    idempotency_key: str


@dataclass
class InterviewRow:
    id: str
    candidate_id: str
    employee_key: str
    project_id: str
    status: str  # Booked | Expired | Passed | Rejected
    booked_at: datetime
    expires_at: datetime
    outcome: str | None = None
    rejection_type: str | None = None
    rejection_reason: str | None = None


@dataclass
class KbRequestRow:
    id: str
    candidate_id: str
    employee_key: str
    project_id: str
    status: str  # Sent | Training | Completed | Failed | Rejected
    training_days: int
    buffer_days: int
    payload: dict
    created_at: datetime
    updated_at: datetime
    reason: str | None = None


@dataclass
class EmployeeBlockRow:
    id: str
    employee_key: str
    candidate_id: str
    demand_id: str
    project_id: str
    actor_id: str
    actor_display_name: str
    status: str
    created_at: datetime
    release_reason: str | None = None
    released_at: datetime | None = None


@dataclass
class HiringRequestRow:
    id: str
    project_id: str
    capability: str
    headcount: int
    justification: str
    status: str
    payload: dict
    created_at: datetime


MNH_SLOT_STATUS = "Hiring from MNH"


def build_mnh_slot_rows(
    hiring_request_id: str,
    project_id: str,
    position_id: str | None,
    capability: str,
    headcount: int,
) -> list["MnhSlotRow"]:
    out: list[MnhSlotRow] = []
    for i in range(max(0, headcount)):
        out.append(
            MnhSlotRow(
                id=_uuid(),
                hiring_request_id=hiring_request_id,
                project_id=project_id,
                position_id=position_id,
                slot_index=i + 1,
                headcount_total=headcount,
                status=MNH_SLOT_STATUS,
                capability=capability,
                created_at=utcnow(),
            )
        )
    return out


def mnh_slots_payload(rows: list["MnhSlotRow"]) -> list[dict]:
    result: list[dict] = []
    for row in rows:
        data = asdict(row)
        for k, v in list(data.items()):
            if isinstance(v, (datetime, date)):
                data[k] = v.isoformat()
        result.append(data)
    return result


def mnh_slot_from_payload(d: dict) -> "MnhSlotRow":
    created = d.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    elif not isinstance(created, datetime):
        created = utcnow()
    return MnhSlotRow(
        id=str(d["id"]),
        hiring_request_id=str(d["hiring_request_id"]),
        project_id=str(d["project_id"]),
        position_id=d.get("position_id"),
        slot_index=int(d["slot_index"]),
        headcount_total=int(d["headcount_total"]),
        status=str(d["status"]),
        capability=str(d["capability"]),
        created_at=created,
    )


def list_mnh_slots_from_hiring(
    hiring_rows: list[HiringRequestRow],
    *,
    project_id: str | None = None,
    position_id: str | None = None,
) -> list["MnhSlotRow"]:
    out: list[MnhSlotRow] = []
    for h in hiring_rows:
        if project_id and h.project_id != project_id:
            continue
        for raw in h.payload.get("mnh_slots") or []:
            if not isinstance(raw, dict):
                continue
            row = mnh_slot_from_payload(raw)
            if position_id and row.position_id != position_id:
                continue
            out.append(row)
    return sorted(out, key=lambda r: (r.position_id or "", r.hiring_request_id, r.slot_index))


@dataclass
class MnhSlotRow:
    id: str
    hiring_request_id: str
    project_id: str
    position_id: str | None
    slot_index: int
    headcount_total: int
    status: str
    capability: str
    created_at: datetime


@dataclass
class OutboxRow:
    id: str
    event_type: str
    payload: dict
    created_at: datetime


class StaffingStore(Protocol):
    def create_demand(self, **kwargs) -> DemandRow: ...
    def get_demand(self, demand_id: str) -> DemandRow | None: ...
    def list_demands(self, project_id: str | None = None) -> list[DemandRow]: ...
    def create_candidate(self, demand_id: str, employee_key: str) -> CandidateRow: ...
    def get_candidate(self, candidate_id: str) -> CandidateRow | None: ...
    def list_candidates(
        self, demand_id: str | None = None, project_id: str | None = None
    ) -> list[CandidateRow]: ...
    def set_candidate_hours(self, candidate_id: str, months: list[dict]) -> CandidateRow: ...
    def update_candidate_status(self, candidate_id: str, status: str) -> None: ...
    def insert_reservation(self, res: ReservationRow) -> None: ...
    def set_candidate_reservations_status(self, candidate_id: str, status: str) -> int: ...
    def insert_outbox(self, event_type: str, payload: dict) -> None: ...
    def list_pending_outbox(self) -> list[OutboxRow]: ...
    def mark_outbox_published(self, ids: list[str]) -> None: ...
    def insert_audit(self, actor: str, action: str, entity_type: str, entity_id: str, details: dict) -> None: ...
    def list_audit(self, limit: int = 100) -> list[dict]: ...
    def reserved_hours_excluding_demand(self, demand_id: str | None) -> dict[tuple[str, int], float]: ...
    def list_reservations(self, candidate_id: str | None = None) -> list[ReservationRow]: ...
    def list_confirmed_reservations(self) -> list[ReservationRow]: ...
    def release_demand(self, project_id: str) -> int: ...
    # interviews
    def create_interview(self, candidate_id: str, expires_at: datetime) -> InterviewRow: ...
    def get_active_interview(self, candidate_id: str) -> InterviewRow | None: ...
    def update_interview(
        self,
        interview_id: str,
        status: str,
        outcome: str | None = None,
        rejection_type: str | None = None,
        rejection_reason: str | None = None,
    ) -> None: ...
    def list_interviews(self, project_id: str | None = None) -> list[InterviewRow]: ...
    def interview_leads_by_employee(self) -> dict[str, int]: ...
    def list_due_interviews(self, now: datetime) -> list[InterviewRow]: ...
    def project_candidate_statuses(self, project_id: str) -> list[tuple[str, str]]: ...
    def project_rejected_employees(self, project_id: str) -> set[str]: ...
    def active_block_holders(self) -> dict[str, list[dict]]: ...
    # knowledge benchmarking
    def create_kb_request(self, candidate_id: str, training_days: int, buffer_days: int, payload: dict, status: str) -> KbRequestRow: ...
    def get_open_kb_request(self, candidate_id: str) -> KbRequestRow | None: ...
    def update_kb_request(
        self, request_id: str, status: str, reason: str | None = None, *, payload: dict | None = None
    ) -> None: ...
    def list_kb_requests(self, project_id: str | None = None) -> list[KbRequestRow]: ...
    # concurrent resource blocks (max N managers per employee)
    def create_employee_block(
        self,
        *,
        employee_key: str,
        candidate_id: str,
        demand_id: str,
        project_id: str,
        actor_id: str,
        actor_display_name: str,
    ) -> EmployeeBlockRow: ...
    def get_active_block_by_candidate(self, candidate_id: str) -> EmployeeBlockRow | None: ...
    def list_active_blocks_for_employee(self, employee_key: str) -> list[EmployeeBlockRow]: ...
    def release_employee_block(self, candidate_id: str, reason: str | None) -> None: ...
    def release_employee_blocks_for_employee(
        self, employee_key: str, *, except_candidate_id: str | None, reason: str
    ) -> None: ...
    def set_employee_block_status(self, candidate_id: str, status: str, reason: str | None = None) -> None: ...
    # MNH
    def create_hiring_request(self, project_id: str, capability: str, headcount: int, justification: str, payload: dict, status: str) -> HiringRequestRow: ...
    def list_hiring_requests(self, project_id: str | None = None) -> list[HiringRequestRow]: ...
    def create_mnh_slots(
        self,
        hiring_request_id: str,
        project_id: str,
        position_id: str | None,
        capability: str,
        headcount: int,
    ) -> list[MnhSlotRow]: ...
    def list_mnh_slots(self, project_id: str | None = None, position_id: str | None = None) -> list[MnhSlotRow]: ...


# ---------------------------------------------------------------------------
# In-memory implementation (unit tests, demo mode)
# ---------------------------------------------------------------------------


def _holder(block_id, actor_id, actor_name, project_id, demand_id, candidate_id, cand_status, booked_at) -> dict:
    """Pool UI shape for one active block (see services.employee_blocks.block_holders_view)."""
    return {
        "block_id": block_id,
        "actor_id": actor_id,
        "actor_display_name": actor_name,
        "project_id": project_id,
        "demand_id": demand_id,
        "candidate_id": candidate_id,
        "candidate_status": cand_status,
        "interview_booked": booked_at is not None,
        "interview_booked_at": booked_at.isoformat() if booked_at else None,
    }


def sort_holders(holders: list[dict]) -> list[dict]:
    return sorted(
        holders,
        key=lambda x: (0 if x["interview_booked"] else 1, x["interview_booked_at"] or "", (x["actor_display_name"] or "").casefold()),
    )


class MemoryStaffingStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.demands: dict[str, DemandRow] = {}
        self.candidates: dict[str, CandidateRow] = {}
        self.reservations: list[ReservationRow] = []
        self.audit: list[dict] = []
        self.outbox: list[dict] = []
        self.interviews: dict[str, InterviewRow] = {}
        self.kb_requests: dict[str, KbRequestRow] = {}
        self.employee_blocks: dict[str, EmployeeBlockRow] = {}
        self._blocks_by_candidate: dict[str, str] = {}
        self.hiring: dict[str, HiringRequestRow] = {}

    # demands
    def create_demand(self, **kwargs) -> DemandRow:
        kwargs.setdefault("status", "open")
        kwargs["start_date"] = str(kwargs["start_date"])[:10]
        kwargs["end_date"] = str(kwargs["end_date"])[:10]
        row = DemandRow(id=_uuid(), candidates=[], **kwargs)
        with self._lock:
            self.demands[row.id] = row
        return row

    def get_demand(self, demand_id: str) -> DemandRow | None:
        return self.demands.get(demand_id)

    def list_demands(self, project_id: str | None = None) -> list[DemandRow]:
        return [d for d in self.demands.values() if not project_id or d.project_id == project_id]

    # candidates
    def create_candidate(self, demand_id: str, employee_key: str) -> CandidateRow:
        row = CandidateRow(id=_uuid(), demand_id=demand_id, employee_key=employee_key.upper(), status="New")
        with self._lock:
            self.candidates[row.id] = row
        return row

    def get_candidate(self, candidate_id: str) -> CandidateRow | None:
        return self.candidates.get(candidate_id)

    def list_candidates(self, demand_id: str | None = None, project_id: str | None = None) -> list[CandidateRow]:
        out = []
        for c in self.candidates.values():
            if demand_id and c.demand_id != demand_id:
                continue
            if project_id:
                d = self.demands.get(c.demand_id)
                if not d or d.project_id != project_id:
                    continue
            out.append(c)
        return out

    def set_candidate_hours(self, candidate_id: str, months: list[dict]) -> CandidateRow:
        c = self.candidates[candidate_id]
        c.months = [CandidateMonthRow(normalize_month_key(m["month_key"]), float(m["hours"])) for m in months]
        return c

    def update_candidate_status(self, candidate_id: str, status: str) -> None:
        self.candidates[candidate_id].status = status

    # reservations
    def insert_reservation(self, res: ReservationRow) -> None:
        with self._lock:
            for existing in self.reservations:
                if existing.idempotency_key == res.idempotency_key:
                    return
            for existing in self.reservations:
                if (
                    existing.employee_key == res.employee_key
                    and existing.month_key == res.month_key
                    and existing.demand_id == res.demand_id
                    and existing.status in ACTIVE_RESERVATION
                ):
                    raise DatabaseError("Reservation conflict")
            self.reservations.append(res)

    def set_candidate_reservations_status(self, candidate_id: str, status: str) -> int:
        n = 0
        with self._lock:
            for r in self.reservations:
                if r.candidate_id == candidate_id and r.status in ACTIVE_RESERVATION and r.status != status:
                    r.status = status
                    n += 1
        return n

    def list_reservations(self, candidate_id: str | None = None) -> list[ReservationRow]:
        return [r for r in self.reservations if not candidate_id or r.candidate_id == candidate_id]

    def reserved_hours_excluding_demand(self, demand_id: str | None) -> dict[tuple[str, int], float]:
        out: dict[tuple[str, int], float] = {}
        for r in self.reservations:
            if r.status not in ACTIVE_RESERVATION:
                continue
            if demand_id and r.demand_id == demand_id:
                continue
            key = (r.employee_key.upper(), month_key_to_int(r.month_key))
            out[key] = out.get(key, 0.0) + r.hours
        return out

    def list_confirmed_reservations(self) -> list[ReservationRow]:
        return [r for r in self.reservations if r.status == "Confirmed"]

    def release_demand(self, project_id: str) -> int:
        n = 0
        with self._lock:
            for d in self.demands.values():
                if d.project_id != project_id:
                    continue
                d.status = "closed"
                for c in self.candidates.values():
                    if c.demand_id == d.id and c.status != "Released":
                        c.status = "Released"
                        n += 1
                for r in self.reservations:
                    if r.demand_id == d.id and r.status in ACTIVE_RESERVATION:
                        r.status = "Released"
        return n

    # outbox / audit
    def insert_outbox(self, event_type: str, payload: dict) -> None:
        self.outbox.append(
            {"id": _uuid(), "event_type": event_type, "payload": payload, "published": False, "created_at": utcnow()}
        )

    def list_pending_outbox(self) -> list[OutboxRow]:
        return [
            OutboxRow(o["id"], o["event_type"], o["payload"], o["created_at"])
            for o in self.outbox
            if not o["published"]
        ]

    def mark_outbox_published(self, ids: list[str]) -> None:
        wanted = set(ids)
        for o in self.outbox:
            if o["id"] in wanted:
                o["published"] = True

    def insert_audit(self, actor: str, action: str, entity_type: str, entity_id: str, details: dict) -> None:
        self.audit.append(
            {
                "id": _uuid(),
                "actor": actor,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "details": details,
                "created_at": utcnow().isoformat(),
            }
        )

    def list_audit(self, limit: int = 100) -> list[dict]:
        return list(reversed(self.audit))[:limit]

    # interviews
    def create_interview(self, candidate_id: str, expires_at: datetime) -> InterviewRow:
        c = self.candidates[candidate_id]
        d = self.demands[c.demand_id]
        row = InterviewRow(
            id=_uuid(),
            candidate_id=candidate_id,
            employee_key=c.employee_key,
            project_id=d.project_id,
            status="Booked",
            booked_at=utcnow(),
            expires_at=expires_at,
        )
        self.interviews[row.id] = row
        return row

    def get_active_interview(self, candidate_id: str) -> InterviewRow | None:
        for i in self.interviews.values():
            if i.candidate_id == candidate_id and i.status == "Booked":
                return i
        return None

    def update_interview(self, interview_id, status, outcome=None, rejection_type=None, rejection_reason=None) -> None:
        i = self.interviews[interview_id]
        i.status = status
        i.outcome = outcome
        i.rejection_type = rejection_type
        i.rejection_reason = rejection_reason

    def list_interviews(self, project_id: str | None = None) -> list[InterviewRow]:
        return [i for i in self.interviews.values() if not project_id or i.project_id == project_id]

    def list_due_interviews(self, now: datetime) -> list[InterviewRow]:
        return [i for i in self.interviews.values() if i.status == "Booked" and i.expires_at <= now]

    def project_candidate_statuses(self, project_id: str) -> list[tuple[str, str]]:
        return [(c.employee_key.upper(), c.status) for c in self.list_candidates(project_id=project_id)]

    def project_rejected_employees(self, project_id: str) -> set[str]:
        return {i.employee_key.upper() for i in self.interviews.values() if i.project_id == project_id and i.status == "Rejected"}

    def active_block_holders(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for b in self.employee_blocks.values():
            if b.status != "Active":
                continue
            cand = self.candidates.get(b.candidate_id)
            booked = [i.booked_at for i in self.interviews.values() if i.candidate_id == b.candidate_id and i.status == "Booked"]
            out.setdefault(b.employee_key.upper(), []).append(
                _holder(b.id, b.actor_id, b.actor_display_name, b.project_id, b.demand_id, b.candidate_id,
                        cand.status if cand else None, min(booked) if booked else None)
            )
        return out

    def interview_leads_by_employee(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.interviews.values():
            if i.status == "Booked":
                out[i.employee_key.upper()] = out.get(i.employee_key.upper(), 0) + 1
        return out

    # KB
    def create_kb_request(self, candidate_id, training_days, buffer_days, payload, status) -> KbRequestRow:
        c = self.candidates[candidate_id]
        d = self.demands[c.demand_id]
        now = utcnow()
        row = KbRequestRow(
            id=_uuid(),
            candidate_id=candidate_id,
            employee_key=c.employee_key,
            project_id=d.project_id,
            status=status,
            training_days=training_days,
            buffer_days=buffer_days,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self.kb_requests[row.id] = row
        return row

    def get_open_kb_request(self, candidate_id: str) -> KbRequestRow | None:
        for r in self.kb_requests.values():
            if r.candidate_id == candidate_id and r.status in ("Sent", "Training", "Rejected"):
                return r
        return None

    def update_kb_request(
        self, request_id: str, status: str, reason: str | None = None, *, payload: dict | None = None
    ) -> None:
        r = self.kb_requests[request_id]
        r.status = status
        r.reason = reason
        if payload is not None:
            r.payload = payload
        r.updated_at = utcnow()

    def list_kb_requests(self, project_id: str | None = None) -> list[KbRequestRow]:
        return [r for r in self.kb_requests.values() if not project_id or r.project_id == project_id]

    # employee blocks
    def create_employee_block(
        self,
        *,
        employee_key: str,
        candidate_id: str,
        demand_id: str,
        project_id: str,
        actor_id: str,
        actor_display_name: str,
    ) -> EmployeeBlockRow:
        now = utcnow()
        row = EmployeeBlockRow(
            id=_uuid(),
            employee_key=employee_key.upper(),
            candidate_id=candidate_id,
            demand_id=demand_id,
            project_id=project_id,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            status="Active",
            created_at=now,
        )
        with self._lock:
            self.employee_blocks[row.id] = row
            self._blocks_by_candidate[candidate_id] = row.id
        return row

    def get_active_block_by_candidate(self, candidate_id: str) -> EmployeeBlockRow | None:
        bid = self._blocks_by_candidate.get(candidate_id)
        if not bid:
            return None
        row = self.employee_blocks.get(bid)
        if row and row.status == "Active":
            return row
        return None

    def list_active_blocks_for_employee(self, employee_key: str) -> list[EmployeeBlockRow]:
        key = employee_key.upper()
        return [
            b
            for b in self.employee_blocks.values()
            if b.employee_key == key and b.status == "Active"
        ]

    def release_employee_block(self, candidate_id: str, reason: str | None) -> None:
        bid = self._blocks_by_candidate.get(candidate_id)
        if not bid:
            return
        row = self.employee_blocks.get(bid)
        if not row or row.status != "Active":
            return
        with self._lock:
            row.status = "Released"
            row.release_reason = reason
            row.released_at = utcnow()

    def release_employee_blocks_for_employee(
        self, employee_key: str, *, except_candidate_id: str | None, reason: str
    ) -> None:
        key = employee_key.upper()
        now = utcnow()
        with self._lock:
            for b in self.employee_blocks.values():
                if b.employee_key != key or b.status != "Active":
                    continue
                if except_candidate_id and b.candidate_id == except_candidate_id:
                    continue
                b.status = "Released"
                b.release_reason = reason
                b.released_at = now

    def set_employee_block_status(self, candidate_id: str, status: str, reason: str | None = None) -> None:
        bid = self._blocks_by_candidate.get(candidate_id)
        if not bid:
            return
        row = self.employee_blocks.get(bid)
        if not row:
            return
        with self._lock:
            row.status = status
            if status != "Active":
                row.release_reason = reason
                row.released_at = utcnow()

    # MNH
    def create_hiring_request(self, project_id, capability, headcount, justification, payload, status) -> HiringRequestRow:
        row = HiringRequestRow(_uuid(), project_id, capability, headcount, justification, status, payload, utcnow())
        self.hiring[row.id] = row
        return row

    def list_hiring_requests(self, project_id: str | None = None) -> list[HiringRequestRow]:
        return [h for h in self.hiring.values() if not project_id or h.project_id == project_id]

    def create_mnh_slots(
        self,
        hiring_request_id: str,
        project_id: str,
        position_id: str | None,
        capability: str,
        headcount: int,
    ) -> list[MnhSlotRow]:
        out = build_mnh_slot_rows(hiring_request_id, project_id, position_id, capability, headcount)
        with self._lock:
            hiring = self.hiring.get(hiring_request_id)
            if hiring:
                hiring.payload = {**hiring.payload, "mnh_slots": mnh_slots_payload(out)}
        return out

    def list_mnh_slots(self, project_id: str | None = None, position_id: str | None = None) -> list[MnhSlotRow]:
        with self._lock:
            rows = list(self.hiring.values())
        return list_mnh_slots_from_hiring(rows, project_id=project_id, position_id=position_id)


# ---------------------------------------------------------------------------
# Azure SQL implementation (dbo.rv_staffing_*)
# ---------------------------------------------------------------------------


def _json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


class AzureStaffingStore:
    """Persists staffing workflow state in dbo.rv_staffing_* on Azure SQL."""

    def _exec(self, sql: str, params: tuple = ()) -> int:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            count = cur.rowcount
            conn.commit()
            return count

    def _batch(self, statements: list[tuple[str, tuple]]) -> None:
        """Run several statements in one transaction."""
        with connect() as conn:
            cur = conn.cursor()
            try:
                for sql, params in statements:
                    cur.execute(sql, params)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        return fetch_rows(sql, params if params else None)

    # demands
    @staticmethod
    def _demand(r: dict) -> DemandRow:
        return DemandRow(
            id=r["Id"],
            project_id=r["ProjectId"],
            proposal_number=r["ProposalNumber"],
            sub_project_name=r["SubProjectName"],
            position_id=r["PositionId"],
            start_date=str(r["StartDate"])[:10],
            end_date=str(r["EndDate"])[:10],
            filters_json=_json(r["FiltersJson"], {}),
            required_skills_json=_json(r["RequiredSkills"], []),
            status=r["Status"],
            created_by=r["CreatedBy"],
        )

    _DEMAND_COLS = (
        "Id, ProjectId, ProposalNumber, SubProjectName, PositionId, StartDate, EndDate, "
        "FiltersJson, RequiredSkills, Status, CreatedBy"
    )

    def create_demand(self, **kwargs) -> DemandRow:
        did = _uuid()
        start, end = str(kwargs["start_date"])[:10], str(kwargs["end_date"])[:10]
        self._exec(
            f"""INSERT INTO dbo.rv_staffing_Demand ({self._DEMAND_COLS})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, N'open', ?)""",
            (
                did,
                kwargs["project_id"],
                kwargs.get("proposal_number"),
                kwargs.get("sub_project_name"),
                kwargs.get("position_id"),
                start,
                end,
                json.dumps(kwargs.get("filters_json") or {}),
                json.dumps(kwargs.get("required_skills_json") or []),
                kwargs["created_by"],
            ),
        )
        return DemandRow(
            id=did,
            project_id=kwargs["project_id"],
            proposal_number=kwargs.get("proposal_number"),
            sub_project_name=kwargs.get("sub_project_name"),
            position_id=kwargs.get("position_id"),
            start_date=start,
            end_date=end,
            filters_json=kwargs.get("filters_json") or {},
            required_skills_json=kwargs.get("required_skills_json") or [],
            status="open",
            created_by=kwargs["created_by"],
        )

    def get_demand(self, demand_id: str) -> DemandRow | None:
        rows = self._query(f"SELECT {self._DEMAND_COLS} FROM dbo.rv_staffing_Demand WHERE Id = ?", (demand_id,))
        return self._demand(rows[0]) if rows else None

    def list_demands(self, project_id: str | None = None) -> list[DemandRow]:
        if project_id:
            rows = self._query(
                f"SELECT {self._DEMAND_COLS} FROM dbo.rv_staffing_Demand WHERE ProjectId = ? ORDER BY CreatedAtUtc DESC",
                (project_id,),
            )
        else:
            rows = self._query(f"SELECT {self._DEMAND_COLS} FROM dbo.rv_staffing_Demand ORDER BY CreatedAtUtc DESC")
        return [self._demand(r) for r in rows]

    # candidates
    def _months_for(self, candidate_ids: list[str]) -> dict[str, list[CandidateMonthRow]]:
        out: dict[str, list[CandidateMonthRow]] = {cid: [] for cid in candidate_ids}
        if not candidate_ids:
            return out
        marks = ",".join("?" for _ in candidate_ids)
        rows = self._query(
            f"SELECT CandidateId, MonthKey, Hours FROM dbo.rv_staffing_CandidateMonth "
            f"WHERE CandidateId IN ({marks}) ORDER BY MonthKey",
            tuple(candidate_ids),
        )
        for m in rows:
            out[m["CandidateId"]].append(CandidateMonthRow(normalize_month_key(m["MonthKey"]), float(m["Hours"])))
        return out

    def _candidates(self, rows: list[dict]) -> list[CandidateRow]:
        months = self._months_for([r["Id"] for r in rows])
        return [
            CandidateRow(
                id=r["Id"],
                demand_id=r["DemandId"],
                employee_key=r["EmployeeKey"],
                status=r["Status"],
                months=months[r["Id"]],
            )
            for r in rows
        ]

    def create_candidate(self, demand_id: str, employee_key: str) -> CandidateRow:
        cid = _uuid()
        self._exec(
            "INSERT INTO dbo.rv_staffing_Candidate (Id, DemandId, EmployeeKey, Status) VALUES (?, ?, ?, N'New')",
            (cid, demand_id, employee_key.upper()),
        )
        return CandidateRow(id=cid, demand_id=demand_id, employee_key=employee_key.upper(), status="New")

    def get_candidate(self, candidate_id: str) -> CandidateRow | None:
        rows = self._query(
            "SELECT Id, DemandId, EmployeeKey, Status FROM dbo.rv_staffing_Candidate WHERE Id = ?", (candidate_id,)
        )
        return self._candidates(rows)[0] if rows else None

    def list_candidates(self, demand_id: str | None = None, project_id: str | None = None) -> list[CandidateRow]:
        sql = (
            "SELECT c.Id, c.DemandId, c.EmployeeKey, c.Status FROM dbo.rv_staffing_Candidate c "
            "JOIN dbo.rv_staffing_Demand d ON d.Id = c.DemandId WHERE 1=1"
        )
        params: list[str] = []
        if demand_id:
            sql += " AND c.DemandId = ?"
            params.append(demand_id)
        if project_id:
            sql += " AND d.ProjectId = ?"
            params.append(project_id)
        sql += " ORDER BY c.CreatedAtUtc DESC"
        return self._candidates(self._query(sql, tuple(params)))

    def set_candidate_hours(self, candidate_id: str, months: list[dict]) -> CandidateRow:
        statements: list[tuple[str, tuple]] = [
            ("DELETE FROM dbo.rv_staffing_CandidateMonth WHERE CandidateId = ?", (candidate_id,))
        ]
        for m in months:
            statements.append(
                (
                    "INSERT INTO dbo.rv_staffing_CandidateMonth (Id, CandidateId, MonthKey, Hours) VALUES (?, ?, ?, ?)",
                    (_uuid(), candidate_id, normalize_month_key(m["month_key"]), float(m["hours"])),
                )
            )
        self._batch(statements)
        cand = self.get_candidate(candidate_id)
        assert cand is not None
        return cand

    def update_candidate_status(self, candidate_id: str, status: str) -> None:
        self._exec("UPDATE dbo.rv_staffing_Candidate SET Status = ? WHERE Id = ?", (status, candidate_id))

    # reservations
    @staticmethod
    def _reservation(r: dict) -> ReservationRow:
        return ReservationRow(
            id=r["Id"],
            candidate_id=r["CandidateId"],
            demand_id=r["DemandId"],
            employee_key=r["EmployeeKey"],
            month_key=normalize_month_key(r["MonthKey"]),
            hours=float(r["Hours"]),
            status=r["Status"],
            idempotency_key=r["IdempotencyKey"],
        )

    _RES_COLS = "Id, CandidateId, DemandId, EmployeeKey, MonthKey, Hours, Status, IdempotencyKey"

    def insert_reservation(self, res: ReservationRow) -> None:
        # Idempotent on IdempotencyKey; unique (EmployeeKey, MonthKey, DemandId) guards double booking.
        exists = self._query(
            "SELECT Id FROM dbo.rv_staffing_Reservation WHERE IdempotencyKey = ?", (res.idempotency_key,)
        )
        if exists:
            return
        try:
            self._exec(
                f"INSERT INTO dbo.rv_staffing_Reservation ({self._RES_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    res.id,
                    res.candidate_id,
                    res.demand_id,
                    res.employee_key,
                    normalize_month_key(res.month_key),
                    res.hours,
                    res.status,
                    res.idempotency_key,
                ),
            )
        except DatabaseError:
            raise
        except Exception as exc:  # pyodbc.IntegrityError and friends
            raise DatabaseError(f"Reservation conflict: {exc}") from exc

    def set_candidate_reservations_status(self, candidate_id: str, status: str) -> int:
        return self._exec(
            "UPDATE dbo.rv_staffing_Reservation SET Status = ? "
            "WHERE CandidateId = ? AND Status IN (N'Reserved', N'Confirmed') AND Status <> ?",
            (status, candidate_id, status),
        )

    def list_reservations(self, candidate_id: str | None = None) -> list[ReservationRow]:
        if candidate_id:
            rows = self._query(
                f"SELECT {self._RES_COLS} FROM dbo.rv_staffing_Reservation WHERE CandidateId = ?", (candidate_id,)
            )
        else:
            rows = self._query(f"SELECT {self._RES_COLS} FROM dbo.rv_staffing_Reservation")
        return [self._reservation(r) for r in rows]

    def reserved_hours_excluding_demand(self, demand_id: str | None) -> dict[tuple[str, int], float]:
        rows = self._query(
            "SELECT EmployeeKey, MonthKey, Hours, DemandId FROM dbo.rv_staffing_Reservation "
            "WHERE Status IN (N'Reserved', N'Confirmed')"
        )
        out: dict[tuple[str, int], float] = {}
        for r in rows:
            if demand_id and r["DemandId"] == demand_id:
                continue
            key = (r["EmployeeKey"].upper(), month_key_to_int(r["MonthKey"]))
            out[key] = out.get(key, 0.0) + float(r["Hours"])
        return out

    def list_confirmed_reservations(self) -> list[ReservationRow]:
        rows = self._query(
            f"SELECT {self._RES_COLS} FROM dbo.rv_staffing_Reservation WHERE Status = N'Confirmed'"
        )
        return [self._reservation(r) for r in rows]

    def release_demand(self, project_id: str) -> int:
        demands = self._query("SELECT Id FROM dbo.rv_staffing_Demand WHERE ProjectId = ?", (project_id,))
        released = 0
        for d in demands:
            released += self._exec(
                "UPDATE dbo.rv_staffing_Candidate SET Status = N'Released' WHERE DemandId = ? AND Status <> N'Released'",
                (d["Id"],),
            )
            self._exec("UPDATE dbo.rv_staffing_Demand SET Status = N'closed' WHERE Id = ?", (d["Id"],))
            self._exec(
                "UPDATE dbo.rv_staffing_Reservation SET Status = N'Released' "
                "WHERE DemandId = ? AND Status IN (N'Reserved', N'Confirmed')",
                (d["Id"],),
            )
        return released

    # outbox / audit
    def insert_outbox(self, event_type: str, payload: dict) -> None:
        self._exec(
            "INSERT INTO dbo.rv_staffing_Outbox (Id, EventType, PayloadJson) VALUES (?, ?, ?)",
            (_uuid(), event_type, json.dumps(payload)),
        )

    def list_pending_outbox(self) -> list[OutboxRow]:
        rows = self._query(
            "SELECT Id, EventType, PayloadJson, CreatedAtUtc FROM dbo.rv_staffing_Outbox "
            "WHERE Published = 0 ORDER BY CreatedAtUtc"
        )
        return [OutboxRow(r["Id"], r["EventType"], _json(r["PayloadJson"], {}), r["CreatedAtUtc"]) for r in rows]

    def mark_outbox_published(self, ids: list[str]) -> None:
        if not ids:
            return
        marks = ",".join("?" for _ in ids)
        self._exec(f"UPDATE dbo.rv_staffing_Outbox SET Published = 1 WHERE Id IN ({marks})", tuple(ids))

    def insert_audit(self, actor: str, action: str, entity_type: str, entity_id: str, details: dict) -> None:
        self._exec(
            """INSERT INTO dbo.rv_staffing_AuditLog
            (Id, Actor, Action, EntityType, EntityId, DetailsJson) VALUES (?, ?, ?, ?, ?, ?)""",
            (_uuid(), actor, action, entity_type, entity_id, json.dumps(details)),
        )

    def list_audit(self, limit: int = 100) -> list[dict]:
        rows = self._query(
            f"SELECT TOP {int(limit)} Id, Actor, Action, EntityType, EntityId, DetailsJson, CreatedAtUtc "
            "FROM dbo.rv_staffing_AuditLog ORDER BY CreatedAtUtc DESC"
        )
        return [
            {
                "id": r["Id"],
                "actor": r["Actor"],
                "action": r["Action"],
                "entity_type": r["EntityType"],
                "entity_id": r["EntityId"],
                "details": _json(r["DetailsJson"], {}),
                "created_at": r["CreatedAtUtc"].isoformat() if r["CreatedAtUtc"] else None,
            }
            for r in rows
        ]

    # interviews
    _INT_SELECT = (
        "SELECT i.Id, i.CandidateId, c.EmployeeKey, d.ProjectId, i.Status, i.BookedAtUtc, i.ExpiresAtUtc, "
        "i.Outcome, i.RejectionType, i.RejectionReason FROM dbo.rv_staffing_Interview i "
        "JOIN dbo.rv_staffing_Candidate c ON c.Id = i.CandidateId "
        "JOIN dbo.rv_staffing_Demand d ON d.Id = c.DemandId"
    )

    @staticmethod
    def _interview(r: dict) -> InterviewRow:
        return InterviewRow(
            id=r["Id"],
            candidate_id=r["CandidateId"],
            employee_key=r["EmployeeKey"],
            project_id=r["ProjectId"],
            status=r["Status"],
            booked_at=r["BookedAtUtc"],
            expires_at=r["ExpiresAtUtc"],
            outcome=r["Outcome"],
            rejection_type=r["RejectionType"],
            rejection_reason=r["RejectionReason"],
        )

    def create_interview(self, candidate_id: str, expires_at: datetime) -> InterviewRow:
        iid = _uuid()
        now = utcnow()
        self._exec(
            "INSERT INTO dbo.rv_staffing_Interview (Id, CandidateId, Status, BookedAtUtc, ExpiresAtUtc) "
            "VALUES (?, ?, N'Booked', ?, ?)",
            (iid, candidate_id, now, expires_at),
        )
        rows = self._query(f"{self._INT_SELECT} WHERE i.Id = ?", (iid,))
        return self._interview(rows[0])

    def get_active_interview(self, candidate_id: str) -> InterviewRow | None:
        rows = self._query(f"{self._INT_SELECT} WHERE i.CandidateId = ? AND i.Status = N'Booked'", (candidate_id,))
        return self._interview(rows[0]) if rows else None

    def update_interview(self, interview_id, status, outcome=None, rejection_type=None, rejection_reason=None) -> None:
        self._exec(
            "UPDATE dbo.rv_staffing_Interview SET Status = ?, Outcome = ?, RejectionType = ?, RejectionReason = ? "
            "WHERE Id = ?",
            (status, outcome, rejection_type, rejection_reason, interview_id),
        )

    def list_interviews(self, project_id: str | None = None) -> list[InterviewRow]:
        if project_id:
            rows = self._query(f"{self._INT_SELECT} WHERE d.ProjectId = ? ORDER BY i.BookedAtUtc DESC", (project_id,))
        else:
            rows = self._query(f"{self._INT_SELECT} ORDER BY i.BookedAtUtc DESC")
        return [self._interview(r) for r in rows]

    def interview_leads_by_employee(self) -> dict[str, int]:
        rows = self._query(
            "SELECT c.EmployeeKey, COUNT(*) AS n FROM dbo.rv_staffing_Interview i "
            "JOIN dbo.rv_staffing_Candidate c ON c.Id = i.CandidateId "
            "WHERE i.Status = N'Booked' GROUP BY c.EmployeeKey"
        )
        return {r["EmployeeKey"].upper(): int(r["n"]) for r in rows}

    def list_due_interviews(self, now: datetime) -> list[InterviewRow]:
        rows = self._query(f"{self._INT_SELECT} WHERE i.Status = N'Booked' AND i.ExpiresAtUtc <= ?", (now,))
        return [self._interview(r) for r in rows]

    def project_candidate_statuses(self, project_id: str) -> list[tuple[str, str]]:
        rows = self._query(
            "SELECT c.EmployeeKey, c.Status FROM dbo.rv_staffing_Candidate c "
            "JOIN dbo.rv_staffing_Demand d ON d.Id = c.DemandId WHERE d.ProjectId = ?",
            (project_id,),
        )
        return [(r["EmployeeKey"].upper(), r["Status"]) for r in rows]

    def project_rejected_employees(self, project_id: str) -> set[str]:
        rows = self._query(
            "SELECT DISTINCT c.EmployeeKey FROM dbo.rv_staffing_Interview i "
            "JOIN dbo.rv_staffing_Candidate c ON c.Id = i.CandidateId "
            "JOIN dbo.rv_staffing_Demand d ON d.Id = c.DemandId "
            "WHERE d.ProjectId = ? AND i.Status = N'Rejected'",
            (project_id,),
        )
        return {r["EmployeeKey"].upper() for r in rows}

    def active_block_holders(self) -> dict[str, list[dict]]:
        """Every active block with its candidate status and earliest booked interview, in one query."""
        rows = self._query(
            "SELECT b.Id, b.EmployeeKey, b.ActorId, b.ActorDisplayName, b.ProjectId, b.DemandId, b.CandidateId, "
            "c.Status AS CandidateStatus, iv.BookedAtUtc "
            "FROM dbo.rv_staffing_EmployeeBlock b "
            "LEFT JOIN dbo.rv_staffing_Candidate c ON c.Id = b.CandidateId "
            "OUTER APPLY (SELECT MIN(i.BookedAtUtc) AS BookedAtUtc FROM dbo.rv_staffing_Interview i "
            "             WHERE i.CandidateId = b.CandidateId AND i.Status = N'Booked') iv "
            "WHERE b.Status = N'Active'"
        )
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["EmployeeKey"].upper(), []).append(
                _holder(r["Id"], r["ActorId"], r["ActorDisplayName"], r["ProjectId"], r["DemandId"],
                        r["CandidateId"], r["CandidateStatus"], r["BookedAtUtc"])
            )
        return out

    # employee blocks
    _BLOCK_SELECT = (
        "SELECT b.Id, b.EmployeeKey, b.CandidateId, b.DemandId, b.ProjectId, b.ActorId, b.ActorDisplayName, "
        "b.Status, b.ReleaseReason, b.CreatedAtUtc, b.ReleasedAtUtc FROM dbo.rv_staffing_EmployeeBlock b "
    )

    @staticmethod
    def _block(r: dict) -> EmployeeBlockRow:
        return EmployeeBlockRow(
            id=r["Id"],
            employee_key=r["EmployeeKey"],
            candidate_id=r["CandidateId"],
            demand_id=r["DemandId"],
            project_id=r["ProjectId"],
            actor_id=r["ActorId"],
            actor_display_name=r["ActorDisplayName"],
            status=r["Status"],
            created_at=r["CreatedAtUtc"],
            release_reason=r["ReleaseReason"],
            released_at=r["ReleasedAtUtc"],
        )

    def create_employee_block(
        self,
        *,
        employee_key: str,
        candidate_id: str,
        demand_id: str,
        project_id: str,
        actor_id: str,
        actor_display_name: str,
    ) -> EmployeeBlockRow:
        bid = _uuid()
        now = utcnow()
        self._exec(
            "INSERT INTO dbo.rv_staffing_EmployeeBlock "
            "(Id, EmployeeKey, CandidateId, DemandId, ProjectId, ActorId, ActorDisplayName, Status, CreatedAtUtc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, N'Active', ?)",
            (bid, employee_key.upper(), candidate_id, demand_id, project_id, actor_id, actor_display_name, now),
        )
        rows = self._query(f"{self._BLOCK_SELECT} WHERE b.Id = ?", (bid,))
        return self._block(rows[0])

    def get_active_block_by_candidate(self, candidate_id: str) -> EmployeeBlockRow | None:
        rows = self._query(
            f"{self._BLOCK_SELECT} WHERE b.CandidateId = ? AND b.Status = N'Active'", (candidate_id,)
        )
        return self._block(rows[0]) if rows else None

    def list_active_blocks_for_employee(self, employee_key: str) -> list[EmployeeBlockRow]:
        rows = self._query(
            f"{self._BLOCK_SELECT} WHERE b.EmployeeKey = ? AND b.Status = N'Active' ORDER BY b.CreatedAtUtc",
            (employee_key.upper(),),
        )
        return [self._block(r) for r in rows]

    def release_employee_block(self, candidate_id: str, reason: str | None) -> None:
        self._exec(
            "UPDATE dbo.rv_staffing_EmployeeBlock SET Status = N'Released', ReleaseReason = ?, ReleasedAtUtc = ? "
            "WHERE CandidateId = ? AND Status = N'Active'",
            (reason, utcnow(), candidate_id),
        )

    def release_employee_blocks_for_employee(
        self, employee_key: str, *, except_candidate_id: str | None, reason: str
    ) -> None:
        sql = (
            "UPDATE dbo.rv_staffing_EmployeeBlock SET Status = N'Released', ReleaseReason = ?, ReleasedAtUtc = ? "
            "WHERE EmployeeKey = ? AND Status = N'Active'"
        )
        params: list = [reason, utcnow(), employee_key.upper()]
        if except_candidate_id:
            sql += " AND CandidateId <> ?"
            params.append(except_candidate_id)
        self._exec(sql, tuple(params))

    def set_employee_block_status(self, candidate_id: str, status: str, reason: str | None = None) -> None:
        self._exec(
            "UPDATE dbo.rv_staffing_EmployeeBlock SET Status = ?, ReleaseReason = ?, ReleasedAtUtc = ? "
            "WHERE CandidateId = ? AND Status = N'Active'",
            (status, reason, utcnow() if status != "Active" else None, candidate_id),
        )

    # KB
    _KB_SELECT = (
        "SELECT k.Id, k.CandidateId, c.EmployeeKey, d.ProjectId, k.Status, k.TrainingDays, k.BufferDays, "
        "k.PayloadJson, k.Reason, k.CreatedAtUtc, k.UpdatedAtUtc FROM dbo.rv_staffing_KbRequest k "
        "JOIN dbo.rv_staffing_Candidate c ON c.Id = k.CandidateId "
        "JOIN dbo.rv_staffing_Demand d ON d.Id = c.DemandId"
    )

    @staticmethod
    def _kb(r: dict) -> KbRequestRow:
        return KbRequestRow(
            id=r["Id"],
            candidate_id=r["CandidateId"],
            employee_key=r["EmployeeKey"],
            project_id=r["ProjectId"],
            status=r["Status"],
            training_days=int(r["TrainingDays"]),
            buffer_days=int(r["BufferDays"]),
            payload=_json(r["PayloadJson"], {}),
            created_at=r["CreatedAtUtc"],
            updated_at=r["UpdatedAtUtc"],
            reason=r["Reason"],
        )

    def create_kb_request(self, candidate_id, training_days, buffer_days, payload, status) -> KbRequestRow:
        kid = _uuid()
        now = utcnow()
        self._exec(
            "INSERT INTO dbo.rv_staffing_KbRequest "
            "(Id, CandidateId, Status, TrainingDays, BufferDays, PayloadJson, CreatedAtUtc, UpdatedAtUtc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kid, candidate_id, status, training_days, buffer_days, json.dumps(payload), now, now),
        )
        return self._kb(self._query(f"{self._KB_SELECT} WHERE k.Id = ?", (kid,))[0])

    def get_open_kb_request(self, candidate_id: str) -> KbRequestRow | None:
        rows = self._query(
            f"{self._KB_SELECT} WHERE k.CandidateId = ? AND k.Status IN (N'Sent', N'Training', N'Rejected') "
            "ORDER BY k.CreatedAtUtc DESC",
            (candidate_id,),
        )
        return self._kb(rows[0]) if rows else None

    def update_kb_request(
        self, request_id: str, status: str, reason: str | None = None, *, payload: dict | None = None
    ) -> None:
        if payload is not None:
            self._exec(
                "UPDATE dbo.rv_staffing_KbRequest SET Status = ?, Reason = ?, PayloadJson = ?, UpdatedAtUtc = ? WHERE Id = ?",
                (status, reason, json.dumps(payload), utcnow(), request_id),
            )
        else:
            self._exec(
                "UPDATE dbo.rv_staffing_KbRequest SET Status = ?, Reason = ?, UpdatedAtUtc = ? WHERE Id = ?",
                (status, reason, utcnow(), request_id),
            )

    def list_kb_requests(self, project_id: str | None = None) -> list[KbRequestRow]:
        if project_id:
            rows = self._query(f"{self._KB_SELECT} WHERE d.ProjectId = ? ORDER BY k.CreatedAtUtc DESC", (project_id,))
        else:
            rows = self._query(f"{self._KB_SELECT} ORDER BY k.CreatedAtUtc DESC")
        return [self._kb(r) for r in rows]

    # MNH
    @staticmethod
    def _hiring(r: dict) -> HiringRequestRow:
        return HiringRequestRow(
            id=r["Id"],
            project_id=r["ProjectId"],
            capability=r["Capability"],
            headcount=int(r["Headcount"]),
            justification=r["Justification"],
            status=r["Status"],
            payload=_json(r["PayloadJson"], {}),
            created_at=r["CreatedAtUtc"],
        )

    def create_hiring_request(self, project_id, capability, headcount, justification, payload, status) -> HiringRequestRow:
        hid = _uuid()
        self._exec(
            "INSERT INTO dbo.rv_staffing_HiringRequest "
            "(Id, ProjectId, Capability, Headcount, Justification, Status, PayloadJson) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (hid, project_id, capability, headcount, justification, status, json.dumps(payload)),
        )
        rows = self._query(
            "SELECT Id, ProjectId, Capability, Headcount, Justification, Status, PayloadJson, CreatedAtUtc "
            "FROM dbo.rv_staffing_HiringRequest WHERE Id = ?",
            (hid,),
        )
        return self._hiring(rows[0])

    def list_hiring_requests(self, project_id: str | None = None) -> list[HiringRequestRow]:
        sql = (
            "SELECT Id, ProjectId, Capability, Headcount, Justification, Status, PayloadJson, CreatedAtUtc "
            "FROM dbo.rv_staffing_HiringRequest"
        )
        if project_id:
            rows = self._query(sql + " WHERE ProjectId = ? ORDER BY CreatedAtUtc DESC", (project_id,))
        else:
            rows = self._query(sql + " ORDER BY CreatedAtUtc DESC")
        return [self._hiring(r) for r in rows]

    def create_mnh_slots(
        self,
        hiring_request_id: str,
        project_id: str,
        position_id: str | None,
        capability: str,
        headcount: int,
    ) -> list[MnhSlotRow]:
        out = build_mnh_slot_rows(hiring_request_id, project_id, position_id, capability, headcount)
        slot_json = mnh_slots_payload(out)
        rows = self._query(
            "SELECT PayloadJson FROM dbo.rv_staffing_HiringRequest WHERE Id = ?",
            (hiring_request_id,),
        )
        if rows:
            payload = _json(rows[0]["PayloadJson"], {})
            payload["mnh_slots"] = slot_json
            self._exec(
                "UPDATE dbo.rv_staffing_HiringRequest SET PayloadJson = ? WHERE Id = ?",
                (json.dumps(payload), hiring_request_id),
            )
        return out

    def list_mnh_slots(self, project_id: str | None = None, position_id: str | None = None) -> list[MnhSlotRow]:
        return list_mnh_slots_from_hiring(
            self.list_hiring_requests(project_id=project_id),
            project_id=project_id,
            position_id=position_id,
        )


_store: StaffingStore | None = None


def get_staffing_store() -> StaffingStore:
    global _store
    if _store is None:
        env_mode = os.environ.get("STAFFING_PERSISTENCE")
        mode = env_mode.strip().lower() if env_mode else get_settings().resolved_staffing_persistence()
        _store = MemoryStaffingStore() if mode == "memory" else AzureStaffingStore()
    return _store


def reset_staffing_store_for_tests() -> None:
    global _store
    _store = MemoryStaffingStore()


def serialize(row: Any) -> dict:
    """Dataclass → JSON-safe dict (datetimes to ISO text)."""
    data = asdict(row)
    for k, v in list(data.items()):
        if isinstance(v, (datetime, date)):
            data[k] = v.isoformat()
    return data
