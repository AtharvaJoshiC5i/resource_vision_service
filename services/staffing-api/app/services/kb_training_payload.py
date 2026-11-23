"""Knowledge Benchmarking SKILL_GAP_TRAINING request body (contract for KB integration)."""

from __future__ import annotations

from datetime import date
from typing import Any

from rv_availability.staffing.skill_compare import skill_match_ticks

from app.services.snapshot import get_availability_snapshot
from app.staffing_store import utcnow

NOT_RECORDED = "NOT_RECORDED"


def _normalize_required(required_skills_json: list) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in required_skills_json or []:
        if isinstance(row, dict):
            name = (row.get("name") or row.get("skill") or "").strip()
            level = (row.get("level") or row.get("required_level") or "").strip()
        else:
            continue
        if name and level:
            out.append((name, level))
    return out


def _skills_map_for_employee(ports, employee_code: str) -> dict[str, str | None]:
    """Skills from dbo.vw_RV_EmployeeSkillsForDashboard (Azure) or stub snapshot."""
    code = (employee_code or "").strip().upper()
    skill_map: dict[str, str | None] = {}
    try:
        for row in ports.skills.get_skills([employee_code]):
            if (row.get("employee_code") or "").strip().upper() != code:
                continue
            name = row.get("skill_name") or row.get("SkillName")
            if not name:
                continue
            level = row.get("current_level") or row.get("skill_level") or row.get("CurrentSkillLevel")
            skill_map[name.casefold()] = level
    except Exception:  # noqa: BLE001
        pass
    return skill_map


def _gap_entries(skill_map: dict[str, str | None], required: list[tuple[str, str]], skill_levels: tuple[str, ...]) -> list[dict]:
    ticks = skill_match_ticks(skill_map, required, order=skill_levels)
    gaps: list[dict] = []
    for t in ticks:
        if t.get("matched"):
            continue
        current = t.get("current_level")
        item: dict[str, Any] = {
            "skill": t["skill"],
            "target_level": t.get("required_level") or t.get("target_level"),
        }
        if current is None:
            item["current_level"] = None
            item["current_level_status"] = NOT_RECORDED
        else:
            norm = str(current).strip()
            if norm.casefold() in {"not documented", "not_documented", ""}:
                item["current_level"] = None
                item["current_level_status"] = NOT_RECORDED
            else:
                item["current_level"] = norm
        gaps.append(item)
    return gaps


def _skill_gap_summary(employee_skill_gaps: list[dict]) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for emp in employee_skill_gaps:
        for g in emp.get("gaps") or []:
            key = (g["skill"], g["target_level"])
            counts[key] = counts.get(key, 0) + 1
    return [
        {"skill": skill, "target_level": level, "employee_count": n}
        for (skill, level), n in sorted(counts.items(), key=lambda x: (x[0][0].casefold(), x[0][1]))
    ]


def _resolve_project_name(project_id: str) -> str:
    snap = get_availability_snapshot()
    for proj in snap.projects.values():
        pid = getattr(proj, "project_id", None) or getattr(proj, "key", None)
        if str(pid).upper() == str(project_id).upper():
            return getattr(proj, "name", None) or str(project_id)
    return str(project_id)


def _resolve_employee_identity(employee_key: str, skill_rows: list[dict]) -> tuple[str, str]:
    snap = get_availability_snapshot()
    key = employee_key.upper()
    emp = snap.employees.get(key)
    if emp:
        return emp.code, emp.name
    if skill_rows:
        code = (skill_rows[0].get("employee_code") or employee_key).strip()
        return code, employee_key
    return employee_key, employee_key


def build_kb_training_payload(
    *,
    request_id: str,
    demand,
    employee_keys: list[str],
    ports,
    skill_levels: tuple[str, ...],
    training_days: int,
    buffer_days: int,
    training_ratio: float,
    request_date: date | None = None,
) -> dict:
    """Build SKILL_GAP_TRAINING payload from live skills view + demand required skills."""
    required = _normalize_required(demand.required_skills_json)
    required_skills = [{"skill": n, "required_level": lv} for n, lv in required]
    total_days = training_days + buffer_days
    pct_train = round(training_ratio * 100) if training_ratio <= 1 else int(training_ratio)
    pct_train = min(100, max(0, pct_train))
    pct_buffer = max(0, 100 - pct_train)

    employee_skill_gaps: list[dict] = []
    for employee_key in employee_keys:
        skill_map = _skills_map_for_employee(ports, employee_key)
        gaps = _gap_entries(skill_map, required, skill_levels) if required else []
        employee_id, employee_name = _resolve_employee_identity(employee_key, ports.skills.get_skills([employee_key]))
        employee_skill_gaps.append(
            {
                "employee_id": employee_id,
                "employee_name": employee_name,
                "gaps": gaps,
            }
        )

    needing = [e for e in employee_skill_gaps if e["gaps"]]

    return {
        "request_id": request_id,
        "project_id": demand.project_id,
        "project_name": _resolve_project_name(demand.project_id),
        "request_type": "SKILL_GAP_TRAINING",
        "request_date": (request_date or utcnow().date()).isoformat(),
        "project_start_date": demand.start_date[:10],
        "project_end_date": demand.end_date[:10],
        "time_window": {
            "total_calendar_days": total_days,
            "training_days": training_days,
            "buffer_days": buffer_days,
            "training_percentage": pct_train,
            "buffer_percentage": pct_buffer,
        },
        "required_skills": required_skills,
        "selected_employee_count": len(employee_keys),
        "employees_requiring_training": len(needing),
        "employee_skill_gaps": employee_skill_gaps,
        "skill_gap_summary": _skill_gap_summary(employee_skill_gaps),
    }


def next_kb_request_id(store, project_id: str) -> str:
    existing = store.list_kb_requests(project_id)
    seq = len(existing) + 1
    slug = "".join(ch if ch.isalnum() else "-" for ch in project_id).strip("-") or "PRJ"
    return f"RV-KB-{slug}-{seq:03d}"