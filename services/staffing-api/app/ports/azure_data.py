"""Azure SQL adapters for the three approved source objects (read-only).

- dbo.project_track_proposals_table
- dbo.zinghr_employee_master
- dbo.vw_RV_EmployeeSkillsForDashboard

SQL text lives in ``app.rv.sql`` and ``app.rv.skills_sql`` (same shapes as Resource Vision POC).
"""

from __future__ import annotations

import logging

from app.database import DatabaseError, fetch_rows
from app.rv import skills as rv_skills
from app.rv.sql import HR_EMPLOYEES, PROJECT_TRACK_ROWS

logger = logging.getLogger("staffing.azure")


class AzureSkillsProvider:
    """Pool skill ticks and levels from dbo.vw_RV_EmployeeSkillsForDashboard."""

    def get_skills(self, employee_codes: list[str]) -> list[dict]:
        snap = rv_skills.get_skills_snapshot()
        if not snap.available:
            logger.warning("Skills view unavailable; pool skill match will be empty")
            return []
        want = {rv_skills.normalize_code(c) for c in employee_codes if c and str(c).strip()}
        if not want:
            return []
        out: list[dict] = []
        for code in want:
            for rec in snap.by_code.get(code, []):
                level = None if rec.level == rv_skills.NOT_DOCUMENTED else rec.level
                out.append(
                    {
                        "employee_code": code,
                        "skill_name": rec.name,
                        "current_level": level,
                    }
                )
        return out

    def get_options(self) -> dict:
        opts = rv_skills.skill_options()
        return {
            "skills": opts.get("names") or [],
            "levels": [lv for lv in opts.get("levels") or [] if lv != rv_skills.NOT_DOCUMENTED],
            "available": opts.get("available", False),
        }

    def refresh(self) -> None:
        rv_skills._state["snapshot"] = None  # noqa: SLF001 — force re-read on next request
        rv_skills._state["checked"] = 0.0


class AzureProjectTrackRead:
    """Fresh PT + ZingHR rows for concurrency / final-check (same queries as the engine)."""

    def fresh_snapshot_rows(self) -> tuple[list[dict], list[dict]]:
        try:
            pt_rows = fetch_rows(PROJECT_TRACK_ROWS)
            hr_rows = fetch_rows(HR_EMPLOYEES)
            return pt_rows, hr_rows
        except DatabaseError:
            logger.exception("Could not refresh Project Track / ZingHR source tables")
            return [], []