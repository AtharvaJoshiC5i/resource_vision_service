"""Concurrent resource blocks (max N managers per employee) until confirm / release / reject.

Identity fields use the IdentityPort contract (`user_id`, `display_name`) so Project Track
can swap the stub for real profiles without schema changes.
"""

from __future__ import annotations

from app.locks import lock_for_employee
from app.state_machine import TERMINAL_STATES
from app.staffing_store import DemandRow, EmployeeBlockRow, StaffingStore

BLOCK_ACTIVE = "Active"
BLOCK_RELEASED = "Released"
BLOCK_CONSUMED = "Consumed"


class EmployeeBlockLimitError(Exception):
    def __init__(self, holders: list[dict], max_slots: int):
        self.holders = holders
        self.max_slots = max_slots


def block_holders_view(store: StaffingStore, employee_key: str) -> list[dict]:
    """Active blocks with interview timing for pool UI (earliest interview first when booked)."""
    key = employee_key.upper()
    rows = store.list_active_blocks_for_employee(key)
    out: list[dict] = []
    for b in rows:
        cand = store.get_candidate(b.candidate_id)
        iv = store.get_active_interview(b.candidate_id)
        if iv and iv.status != "Booked":
            iv = None
        out.append(
            {
                "block_id": b.id,
                "actor_id": b.actor_id,
                "actor_display_name": b.actor_display_name,
                "project_id": b.project_id,
                "demand_id": b.demand_id,
                "candidate_id": b.candidate_id,
                "candidate_status": cand.status if cand else None,
                "interview_booked": iv is not None,
                "interview_booked_at": iv.booked_at.isoformat() if iv else None,
            }
        )
    out.sort(
        key=lambda x: (
            0 if x["interview_booked"] else 1,
            x["interview_booked_at"] or "",
            x["actor_display_name"].casefold(),
        )
    )
    return out


def create_candidate_with_block(
    store: StaffingStore,
    demand: DemandRow,
    employee_key: str,
    actor_id: str,
    actor_display_name: str,
    max_slots: int,
):
    """Reserve one block slot and create (or return) the in-flight candidate for this demand."""
    from app.staffing_store import CandidateRow

    key = employee_key.upper()
    with lock_for_employee(key):
        for existing in store.list_candidates(demand_id=demand.id):
            if existing.employee_key == key and existing.status not in TERMINAL_STATES:
                block = store.get_active_block_by_candidate(existing.id)
                if block is None:
                    block = store.create_employee_block(
                        employee_key=key,
                        candidate_id=existing.id,
                        demand_id=demand.id,
                        project_id=demand.project_id,
                        actor_id=actor_id,
                        actor_display_name=actor_display_name,
                    )
                return existing, block

        active = store.list_active_blocks_for_employee(key)
        if len(active) >= max_slots:
            raise EmployeeBlockLimitError(block_holders_view(store, key), max_slots)

        cand: CandidateRow = store.create_candidate(demand.id, key)
        block = store.create_employee_block(
            employee_key=key,
            candidate_id=cand.id,
            demand_id=demand.id,
            project_id=demand.project_id,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
        )
        return cand, block


def release_block_for_candidate(store: StaffingStore, candidate_id: str, reason: str | None = None) -> None:
    store.release_employee_block(candidate_id, reason or "released")


def on_employee_confirmed(store: StaffingStore, employee_key: str, winning_candidate_id: str) -> None:
    """Winning confirmation consumes this block and frees all other active blocks on the employee."""
    with lock_for_employee(employee_key):
        store.set_employee_block_status(winning_candidate_id, BLOCK_CONSUMED)
        store.release_employee_blocks_for_employee(
            employee_key,
            except_candidate_id=winning_candidate_id,
            reason="another_project_confirmed",
        )