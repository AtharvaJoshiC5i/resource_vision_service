from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rv_availability import engine as e
from rv_availability import views as v
from rv_availability.staffing.bench_class import bench_class
from rv_availability.staffing.bookable_hours import bookable_hours_for_month
from rv_availability.staffing.eligibility import eligibility_result
from rv_availability.staffing.launch_filters import employee_matches_launch_filters
from rv_availability.staffing.skill_compare import DEFAULT_LEVEL_ORDER, skill_match_ticks


BENCH_RANK = {
    "True Bench": 0,
    "Future Bench": 1,
    "Partially Allocated": 2,
    "In Project": 3,
}


@dataclass
class RankedEmployee:
    employee_key: str
    employee_code: str
    employee_name: str
    bench_class: str
    bookable_by_month: dict[int, float]
    skill_ticks: list[dict]
    eligible: bool
    eligibility_reasons: list[str]
    rank_score: tuple[Any, ...]


def rank_candidates(
    snap: e.Snapshot,
    filters: v.Filters,
    required_skills: list[tuple[str, str]],
    project_months: list[int],
    *,
    reserved_by_employee_month: dict[tuple[str, int], float] | None = None,
    employee_skills: dict[str, dict[str, str | None]] | None = None,
    skill_level_order: tuple[str, ...] | None = None,
    include_ineligible: bool = False,
) -> list[RankedEmployee]:
    reserved_by_employee_month = reserved_by_employee_month or {}
    employee_skills = employee_skills or {}
    order = skill_level_order

    rows: list[RankedEmployee] = []
    for emp in snap.employees.values():
        if not _employee_ok_basic(snap, emp, filters):
            continue
        elig = eligibility_result(emp, project_months)
        eligible = bool(elig["eligible"])
        if not eligible and not include_ineligible:
            continue

        skills_row = employee_skills.get(emp.key, {})
        ticks = skill_match_ticks(
            skills_row,
            required_skills,
            order=order or DEFAULT_LEVEL_ORDER,
        ) if required_skills else []

        bookable: dict[int, float] = {}
        total_bookable = 0.0
        for m in project_months:
            em = snap.employee_months.get((emp.key, m))
            res = reserved_by_employee_month.get((emp.key, m), 0.0)
            h = bookable_hours_for_month(em, emp, reserved_hours=res)
            bookable[m] = h
            total_bookable += h

        bench = bench_class(snap, emp)
        skill_match_count = sum(1 for t in ticks if t["matched"])
        bench_rank = BENCH_RANK.get(bench, 99)
        score = (
            0 if eligible else 1,
            bench_rank,
            -skill_match_count,
            -total_bookable,
            emp.code,
        )
        rows.append(
            RankedEmployee(
                employee_key=emp.key,
                employee_code=emp.code,
                employee_name=emp.name,
                bench_class=bench,
                bookable_by_month=bookable,
                skill_ticks=ticks,
                eligible=eligible,
                eligibility_reasons=list(elig["reasons"]),
                rank_score=score,
            )
        )

    rows.sort(key=lambda r: r.rank_score)
    return rows


def _employee_ok_basic(snap: e.Snapshot, emp: e.Employee, f: v.Filters) -> bool:
    return employee_matches_launch_filters(snap, emp, f)