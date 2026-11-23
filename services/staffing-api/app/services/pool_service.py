from __future__ import annotations

from datetime import date

from rv_availability import engine as e
from rv_availability import views as v
from rv_availability.staffing.bookable_hours import bookable_hours_for_month
from rv_availability.staffing.launch_filters import (
    filters_from_launch_payload,
    launch_filters_empty,
    launch_filters_summary,
)
from rv_availability.staffing.ranking import rank_candidates

from app.config import get_settings
from app.runtime import resolved_rv_data_source
from app.staffing_store import sort_holders
from app.services.snapshot import get_availability_snapshot, reserved_hours_map
from app.staffing_store import StaffingStore


NOT_DOCUMENTED = "Not documented"


def skill_vocabulary(ports, configured: tuple[str, ...]) -> dict:
    """Skill names and levels as they exist in the skills view.

    Levels the view uses are listed with the configured (ranked) ones first, in configured
    order, then any other level the view contains. Levels outside the configured order cannot
    be ranked and only match on equal text.
    """
    try:
        opts = ports.skills.get_options()
    except Exception:  # noqa: BLE001 - skills view being down must not break the pool
        opts = {}
    source = [lv for lv in opts.get("levels") or [] if lv != NOT_DOCUMENTED]
    folded = {lv.casefold() for lv in source}
    ranked = [lv for lv in configured if not source or lv.casefold() in folded]
    extra = sorted((lv for lv in source if lv.casefold() not in {c.casefold() for c in configured}), key=str.casefold)
    return {
        "names": opts.get("skills") or [],
        "levels": ranked + extra,
        "unranked_levels": extra,
        "available": bool(opts.get("available", True)),
    }


def _data_sources() -> list[dict]:
    mode = resolved_rv_data_source()
    azure = mode != "demo"
    skills_status = "azure" if azure else "stub"
    return [
        {"id": "project_track", "label": "dbo.project_track_proposals_table", "status": "azure" if azure else "demo"},
        {"id": "zinghr", "label": "dbo.zinghr_employee_master", "status": "azure" if azure else "demo"},
        {
            "id": "rv2_facts",
            "label": "dbo.rv2_*" if mode == "azure" else "engine (PT+HR)" if mode == "azure_raw" else "demo",
            "status": "azure" if azure else "demo",
        },
        {"id": "skills", "label": "dbo.vw_RV_EmployeeSkillsForDashboard", "status": skills_status},
        {"id": "kb", "label": "Knowledge Benchmarking", "status": "stub"},
        {"id": "mnh", "label": "MyNextHire", "status": "stub"},
    ]


def _project_months(month_hours: list[dict], snap) -> list[int]:
    months = []
    for row in month_hours:
        mk = row["month_key"]
        if isinstance(mk, str):
            months.append(e.month_int(date.fromisoformat(mk[:10])))
        else:
            months.append(int(mk))
    if not months:
        months = list(snap.window[:6])
    return months


def _month_cells(snap, emp_key: str, months: list[int], reserved) -> list[dict]:
    emp = snap.employees.get(emp_key.upper())
    if not emp:
        return []
    cells = []
    for m in months:
        em = snap.employee_months.get((emp.key, m))
        res = reserved.get((emp.key, m), 0.0)
        bookable = bookable_hours_for_month(em, emp, reserved_hours=res)
        cells.append(
            {
                "month_key": m,
                "label": v.month_label(m),
                "status": em.status if em else "No record",
                "remaining": em.remaining if em else None,
                "bookable_hours": bookable,
            }
        )
    return cells


def _match_search(emp: e.Employee, q: str) -> bool:
    if not q:
        return True
    needle = q.strip().casefold()
    return needle in emp.code.casefold() or needle in emp.name.casefold()


def _availability_filter(cells: list[dict], mode: str) -> bool:
    if mode == "all":
        return True
    has = [c["bookable_hours"] > 0 for c in cells]
    if not has:
        return mode == "all"
    return all(has) if mode == "every" else any(has)


def _skill_match_filter(ticks: list[dict], mode: str) -> bool:
    if mode == "all" or not ticks:
        return True
    matched = sum(1 for t in ticks if t.get("matched"))
    if mode == "full":
        return matched == len(ticks)
    return matched > 0


def search_pool(store: StaffingStore, body: dict, skill_levels: tuple[str, ...], ports) -> dict:
    snap = get_availability_snapshot()
    filters = filters_from_launch_payload(body.get("filters"))
    applied_filters = launch_filters_summary(filters)
    required = [(s["name"], s["level"]) for s in body.get("required_skills", [])]
    project_months = _project_months(body.get("month_hours", []), snap)

    skills_by_emp: dict[str, dict[str, str | None]] = {}
    skill_lists: dict[str, dict[str, str]] = {}
    codes = [emp.code for emp in snap.employees.values()]
    for row in ports.skills.get_skills(codes):
        key = row["employee_code"].upper()
        level = row.get("current_level")
        skills_by_emp.setdefault(key, {})[row["skill_name"].casefold()] = level
        # Shown exactly as stored in the skills view; a NULL level is "Not documented".
        skill_lists.setdefault(key, {})[row["skill_name"]] = level or NOT_DOCUMENTED

    from app.orchestrator import expire_interviews
    from app.state_machine import TERMINAL_STATES

    expire_interviews(store)
    project_id = body.get("project_id")
    block_max = get_settings().employee_block_max
    leads = store.interview_leads_by_employee()
    in_flight: dict[str, str] = {}
    rejected: set[str] = set()
    if project_id:
        for key, status in store.project_candidate_statuses(project_id):
            if status == "Rejected":
                rejected.add(key)
            elif status not in TERMINAL_STATES:
                in_flight[key] = status
        rejected |= store.project_rejected_employees(project_id)
    holders_by_employee = store.active_block_holders()

    reserved = reserved_hours_map(store)
    show_entire_pool = launch_filters_empty(filters) and not required
    ranked = rank_candidates(
        snap,
        filters,
        required,
        project_months,
        reserved_by_employee_month=reserved,
        employee_skills=skills_by_emp,
        skill_level_order=skill_levels,
        include_ineligible=show_entire_pool,
    )

    search = (body.get("search") or "").strip()
    avail_mode = body.get("availability_filter") or "all"
    skill_mode = body.get("skill_match_filter") or "all"

    employees_out = []
    for r in ranked:
        emp = snap.employees.get(r.employee_key.upper())
        if not emp:
            continue
        if r.employee_key.upper() in rejected:
            continue
        cells = _month_cells(snap, r.employee_key, project_months, reserved)
        if not _match_search(emp, search):
            continue
        if not _availability_filter(cells, avail_mode):
            continue
        if not _skill_match_filter(r.skill_ticks, skill_mode):
            continue
        key_u = r.employee_key.upper()
        active_blocks = sort_holders(holders_by_employee.get(key_u, []))
        slots_remaining = max(0, block_max - len(active_blocks))
        on_this_project = key_u in in_flight
        employees_out.append(
            {
                "employee_key": r.employee_key,
                "employee_code": r.employee_code,
                "employee_name": r.employee_name,
                "bench_class": r.bench_class,
                "primary_capability": emp.primary_capability,
                "secondary_capability": emp.secondary_capability,
                "department": emp.department,
                "grade": emp.grade,
                "location": emp.location,
                "country": emp.country,
                "bookable_by_month": {str(k): v for k, v in r.bookable_by_month.items()},
                "skill_ticks": r.skill_ticks,
                "skills": [
                    {"name": n, "level": lv}
                    for n, lv in sorted(skill_lists.get(r.employee_key.upper(), {}).items(), key=lambda t: t[0].casefold())
                ],
                "months": cells,
                "interview_leads_count": leads.get(key_u, 0),
                "in_flight_status": in_flight.get(key_u),
                "block_slots_max": block_max,
                "block_slots_active": len(active_blocks),
                "block_slots_remaining": slots_remaining,
                "can_block": slots_remaining > 0 or on_this_project,
                "active_blocks": active_blocks,
            }
        )

    if not employees_out and body.get("allow_mnh"):
        mnh = ports.mnh.request_hire({"demand": body})
        return {"employees": [], "mnh": mnh, "data_sources": _data_sources()}

    return {
        "employees": employees_out,
        "meta": {
            "count": len(employees_out),
            "project_months": project_months,
            "capacity_hours": e.CAPACITY_HOURS,
            "window": snap.window,
            "applied_filters": applied_filters,
            "ranked_before_client_filters": len(ranked),
            "unfiltered_pool": show_entire_pool,
        },
        "data_sources": _data_sources(),
    }