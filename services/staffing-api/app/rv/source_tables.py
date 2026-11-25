"""Availability snapshot straight from the two source tables (RV_DATA_SOURCE=source_tables).

Reads only:
  - dbo.project_track_proposals_table
  - dbo.zinghr_employee_master

No views, stored procedures, helper functions or precomputed tables are needed in the database.
Text cleanup that the other modes do with dbo.rv_Blank / rv_Clean / rv_Key happens here in
Python (``clean`` / ``employee_key``), applied to rows that SQL has already reduced.

Why it stays fast on a large database
-------------------------------------
* Detail rows are read for the 19-month reporting window only (a range filter on month_key),
  never the whole Project Track history.
* Everything that needs every month (the employee "latest real name" lookup, the project
  dimension, contract types) is reduced inside SQL to one row per employee / project, so only
  small results cross the network.
* All six reads run at the same time, each on its own pooled connection.
* A one-row change fingerprint (row counts + checksums) decides whether a reload is needed; the
  API keeps serving the current snapshot while a reload runs in the background.

Cleanup rule (keep in step with the SQL fragments below)
--------------------------------------------------------
``clean``: trim surrounding whitespace; empty text and the literal text "null" (any case) become
NULL. ``employee_key``: the cleaned code in upper case. These mirror what the dbo.rv_* helpers
are understood to do. If the real helper definitions differ, change ``clean`` /
``employee_key`` and ``_CLEAN`` / ``_KEY`` together; nothing else depends on the rule.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

from rv_availability import engine as e

from app.database import fetch_rows

logger = logging.getLogger("resource_vision")

PT = "dbo.project_track_proposals_table"
HR = "dbo.zinghr_employee_master"
_BIN = "Latin1_General_100_BIN2"  # code-point order, same as Python string comparison


# --------------------------------------------------------------------------- Python cleanup
def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = (value if isinstance(value, str) else str(value)).strip()
    if not text or text.lower() == "null":
        return None
    return text


def employee_key(value: Any) -> str | None:
    text = clean(value)
    return text.upper() if text else None


# --------------------------------------------------------------------------- SQL fragments
def _CLEAN(column: str, size: int = 450) -> str:  # noqa: N802 - SQL macro
    trimmed = f"LTRIM(RTRIM(CAST({column} AS nvarchar({size}))))"
    return f"(CASE WHEN LOWER({trimmed}) IN (N'', N'null') THEN NULL ELSE {trimmed} END)"


def _KEY(column: str) -> str:  # noqa: N802 - SQL macro
    return f"UPPER({_CLEAN(column)})"


def _MONTH_INT(column: str) -> str:  # noqa: N802 - SQL macro
    return f"(YEAR({column}) * 100 + MONTH({column}))"


def _FIRST(column: str, alias: str, condition: str = "1 = 1", size: int = 1990) -> str:  # noqa: N802
    """First non-null value in ``pfx`` order: MIN over 'zero-padded rank + value', then strip
    the 10-character rank. Ranks are unique per group, so the value never decides the order."""
    return (
        f"{alias} = SUBSTRING(MIN(CASE WHEN {condition} AND {column} IS NOT NULL "
        f"THEN pfx + CAST({column} AS nvarchar({size})) END), 11, {size})"
    )


def _PFX(partition: str, order: str) -> str:  # noqa: N802
    return (
        f"pfx = RIGHT('0000000000' + CAST(ROW_NUMBER() OVER (PARTITION BY {partition} "
        f"ORDER BY {order}) AS varchar(10)), 10)"
    )


# Named Project Track rows inside the reporting window. Parameters: window start (inclusive),
# first day after the window (exclusive). Plain columns only, so an index on month_key can be used.
WINDOW_ROWS = f"""
SELECT row_id, project_id, proposal_number, sub_project_name, employee_id, month_key,
       effort = CAST(effort_value AS float), is_override, contract_type, start_date, end_date
FROM {PT}
WHERE month_key >= ? AND month_key < ? AND employee_id IS NOT NULL
"""

# Window months that hold any Project Track row (named or not).
MONTHS_WITH_DATA = f"""
SELECT DISTINCT month_int = {_MONTH_INT("month_key")}
FROM {PT}
WHERE month_key >= ? AND month_key < ?
"""

# One row per Project Track employee id over every month: display code, plus the attributes of
# the latest-month row whose name is a real name (not the id itself); blanks never win.
# Same ordering as engine._lookup: month (newest first), then row id.
EMPLOYEE_LOOKUP = f"""
WITH P AS (
    SELECT k    = {_KEY("employee_id")},
           code = {_CLEAN("employee_id")},
           n    = {_CLEAN("employee_name", 1000)},
           pc   = {_CLEAN("primary_capability", 1000)},
           sc   = {_CLEAN("secondary_capability", 1000)},
           dp   = {_CLEAN("department", 1000)},
           gr   = {_CLEAN("grade", 1000)},
           lc   = {_CLEAN("location", 1000)},
           co   = {_CLEAN("country", 1000)},
           mk   = {_MONTH_INT("month_key")},
           rid  = {_CLEAN("row_id")}
    FROM {PT}
    WHERE employee_id IS NOT NULL
), R AS (
    SELECT P.*, is_real = CASE WHEN n IS NOT NULL AND UPPER(n) <> k THEN 1 ELSE 0 END
    FROM P
    WHERE k IS NOT NULL
), O AS (
    SELECT R.*,
           {_PFX("k", f"is_real DESC, CASE WHEN mk IS NULL THEN 1 ELSE 0 END, mk DESC, "
                      f"CASE WHEN rid IS NULL THEN 1 ELSE 0 END, rid COLLATE {_BIN}")}
    FROM R
)
SELECT employee_code = MIN(code),
       {_FIRST("n", "employee_name", "is_real = 1")},
       {_FIRST("pc", "primary_capability", "is_real = 1")},
       {_FIRST("sc", "secondary_capability", "is_real = 1")},
       {_FIRST("dp", "department", "is_real = 1")},
       {_FIRST("gr", "grade", "is_real = 1")},
       {_FIRST("lc", "location", "is_real = 1")},
       {_FIRST("co", "country", "is_real = 1")}
FROM O
GROUP BY k
"""

# One row per project over every month: first non-blank value per attribute in row-id order,
# earliest start and latest end (same rules as engine.build_projects).
PROJECT_DIMENSION = f"""
WITH P AS (
    SELECT pid            = {_CLEAN("project_id")},
           rid            = {_CLEAN("row_id")},
           project_name   = {_CLEAN("project_name", 1000)},
           parent_account = {_CLEAN("parent_account_name", 1000)},
           account        = {_CLEAN("account_name", 1000)},
           bdu            = {_CLEAN("bdu_name", 1000)},
           project_status = {_CLEAN("project_status", 1000)},
           project_lead   = {_CLEAN("project_lead_name", 1000)},
           notes          = {_CLEAN("notes", 3990)},
           start_date, end_date
    FROM {PT}
    WHERE project_id IS NOT NULL
), O AS (
    SELECT P.*, {_PFX("pid", f"CASE WHEN rid IS NULL THEN 1 ELSE 0 END, rid COLLATE {_BIN}")}
    FROM P
    WHERE pid IS NOT NULL
)
SELECT project_id = pid,
       {_FIRST("project_name", "project_name")},
       {_FIRST("parent_account", "parent_account")},
       {_FIRST("account", "account")},
       {_FIRST("bdu", "bdu")},
       {_FIRST("project_status", "project_status")},
       {_FIRST("project_lead", "project_lead")},
       {_FIRST("notes", "notes", size=3990)},
       start_date = MIN(start_date),
       end_date   = MAX(end_date)
FROM O
GROUP BY pid
"""

# Distinct contract types per project (case-sensitive, like the Python set it replaces).
PROJECT_CONTRACT_TYPES = f"""
SELECT DISTINCT project_id    = {_CLEAN("project_id")},
                contract_type = {_CLEAN("contract_type")} COLLATE {_BIN}
FROM {PT}
WHERE project_id IS NOT NULL AND contract_type IS NOT NULL
"""

HR_EMPLOYEES = f"""
SELECT EmployeeCode, EmployeeName,
       joining_date     = CAST(DateOfJoining AS date),
       exit_date        = CAST(ExitDate AS date),
       leaving_date     = CAST(DateOfLeaving AS date),
       resignation_date = CAST(DateofResignation AS date),
       EmployeeStatus, [Primary Practice], [Secondary Practice], [Grade Code], COUNTRY, Location,
       Division, Department, Email, ReportingManagerName, ReportingManagerCode, EmploymentType,
       [Business Vertical]
FROM {HR}
WHERE EmployeeCode IS NOT NULL
"""

# One small row that changes when either table changes. BINARY_CHECKSUM(*) skips column types it
# cannot compare. A checksum can miss a change in rare cases, so a full reload also runs on a
# timer (RV_SOURCE_MAX_AGE_SECONDS).
FINGERPRINT = f"""
SELECT pt_rows = (SELECT COUNT_BIG(*) FROM {PT}),
       pt_sum  = (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(*)) FROM {PT}),
       hr_rows = (SELECT COUNT_BIG(*) FROM {HR}),
       hr_sum  = (SELECT CHECKSUM_AGG(BINARY_CHECKSUM(*)) FROM {HR})
"""

_HR_TEXT = {
    "employee_name": "EmployeeName",
    "employee_status": "EmployeeStatus",
    "primary_capability": "Primary Practice",
    "secondary_capability": "Secondary Practice",
    "grade": "Grade Code",
    "country": "COUNTRY",
    "location": "Location",
    "division": "Division",
    "department": "Department",
    "email": "Email",
    "manager_name": "ReportingManagerName",
    "manager_code": "ReportingManagerCode",
    "employment_type": "EmploymentType",
    "business_vertical": "Business Vertical",
}
_LOOKUP_ATTRS = (
    "employee_name", "primary_capability", "secondary_capability",
    "department", "grade", "location", "country",
)


# --------------------------------------------------------------------------- row shaping
def window_bounds(today: date, window_months: int = e.WINDOW_MONTHS) -> tuple[date, date]:
    window = e.build_window(today, window_months)
    return e.month_start(window[0]), e.month_end(window[-1]) + timedelta(days=1)


def shape_pt_row(r: dict[str, Any]) -> dict[str, Any] | None:
    key = employee_key(r.get("employee_id"))
    if key is None:
        return None
    return {
        "row_id": clean(r.get("row_id")),
        "project_id": clean(r.get("project_id")),
        "proposal_number": r.get("proposal_number"),
        "sub_project_name": r.get("sub_project_name"),
        "employee_key": key,
        "employee_code": clean(r.get("employee_id")),
        "month_key": r.get("month_key"),
        "effort": r.get("effort"),
        "is_override": r.get("is_override"),
        "contract_type": clean(r.get("contract_type")),
        "start_date": r.get("start_date"),
        "end_date": r.get("end_date"),
    }


def shape_hr_row(r: dict[str, Any]) -> dict[str, Any]:
    row = {name: clean(r.get(column)) for name, column in _HR_TEXT.items()}
    row.update(
        employee_key=employee_key(r.get("EmployeeCode")),
        employee_code=clean(r.get("EmployeeCode")),
        joining_date=r.get("joining_date"),
        exit_date=r.get("exit_date"),
        leaving_date=r.get("leaving_date"),
        resignation_date=r.get("resignation_date"),
    )
    return row


def shape_lookup(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, str | None]], dict[str, str]]:
    lookup: dict[str, dict[str, str | None]] = {}
    codes: dict[str, str] = {}
    for r in rows:
        code = clean(r.get("employee_code"))
        key = employee_key(code)
        if key is None or key in codes:
            continue
        codes[key] = code
        lookup[key] = {attr: clean(r.get(attr)) for attr in _LOOKUP_ATTRS}
    return lookup, codes


# --------------------------------------------------------------------------- loading
def read_all(today: date, window_months: int = e.WINDOW_MONTHS) -> dict[str, list[dict[str, Any]]]:
    """The six reads, run at the same time."""
    start, after = window_bounds(today, window_months)
    jobs = {
        "window_rows": (WINDOW_ROWS, (start, after)),
        "months": (MONTHS_WITH_DATA, (start, after)),
        "lookup": (EMPLOYEE_LOOKUP, None),
        "projects": (PROJECT_DIMENSION, None),
        "contract_types": (PROJECT_CONTRACT_TYPES, None),
        "hr": (HR_EMPLOYEES, None),
    }
    with ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="rv-source") as pool:
        futures = {name: pool.submit(fetch_rows, sql, params) for name, (sql, params) in jobs.items()}
        return {name: f.result() for name, f in futures.items()}


def snapshot_from_results(
    data: dict[str, list[dict[str, Any]]],
    today: date,
    capacity_hours: float = e.CAPACITY_HOURS,
    window_months: int = e.WINDOW_MONTHS,
) -> e.Snapshot:
    """Assemble the snapshot from the six query results (no database access; unit tested)."""
    lookup, codes = shape_lookup(data["lookup"])
    pt_rows = [row for row in map(shape_pt_row, data["window_rows"]) if row is not None]
    project_rows = [{k: clean(v) if isinstance(v, str) else v for k, v in r.items()} for r in data["projects"]]
    type_rows = [
        {"project_id": clean(r.get("project_id")), "contract_type": clean(r.get("contract_type"))}
        for r in data["contract_types"]
    ]
    return e.build_snapshot_from_parts(
        pt_rows,
        [shape_hr_row(r) for r in data["hr"]],
        today,
        lookup=lookup,
        pt_codes=codes,
        projects=e.build_projects_from_dimension(project_rows, type_rows),
        months_with_data={int(r["month_int"]) for r in data["months"] if r.get("month_int") is not None},
        capacity_hours=capacity_hours,
        window_months=window_months,
    )


def load_snapshot(today: date, capacity_hours: float = e.CAPACITY_HOURS) -> e.Snapshot:
    return snapshot_from_results(read_all(today), today, capacity_hours)


def read_fingerprint() -> tuple:
    rows = fetch_rows(FINGERPRINT)
    r = rows[0] if rows else {}
    return (r.get("pt_rows"), r.get("pt_sum"), r.get("hr_rows"), r.get("hr_sum"))
