"""RV_DATA_SOURCE=source_tables: parity with the full-row engine, SQL scope and reload rules.

Synthetic data only. No database is contacted: the six SQL results are produced in Python from
synthetic source-table rows, following what each query is written to return.
"""

from __future__ import annotations

import random
import re
import time
from collections import defaultdict
from datetime import date

import pytest
from rv_availability import engine as e

from app.rv import service as rv_service
from app.rv import source_tables as st
from app.rv.source_tables import clean, employee_key

TODAY = date(2026, 11, 25)
CAPS = ["Pharma CI", "Data Science", "Market Access", "Analytics"]
CONTRACTS = ["T&M-FTE", "T&M-Hrs", "Output-EffortBased", " t&m-fte ", "Retainer", None]


# --------------------------------------------------------------------------- synthetic source rows
def synthetic_sources(employees: int, projects: int, rows_per_emp_month: int = 2, seed: int = 7):
    """Source-shaped rows (real column names) with the mess the cleanup must handle: padded
    and lower-case ids, 'null' text, rows before and after the window, a non-first-day
    month_key, conflicting duplicates, Project Track ids missing from ZingHR, duplicated HR
    codes and leavers."""
    rnd = random.Random(seed)
    window = e.build_window(TODAY)
    months = [e.add_months(window[0], -6 + i) for i in range(len(window) + 9)]  # 6 before, 3 after
    pt: list[dict] = []
    hr: list[dict] = []
    rid = 0
    for i in range(employees):
        code = f"E{i:05d}"
        if i % 37 != 0:  # some PT ids have no ZingHR record
            hr.append({
                "EmployeeCode": f" {code.lower()} " if i % 11 == 0 else code,
                "EmployeeName": f"Employee {i}" if i % 13 else "null",
                "joining_date": date(2018 + i % 8, 1 + i % 12, 1),
                "exit_date": date(2027, 3, 31) if i % 29 == 0 else None,
                "leaving_date": None,
                "resignation_date": None,
                "EmployeeStatus": "FnF" if i % 29 == 0 else "Active",
                "Primary Practice": CAPS[i % 4],
                "Secondary Practice": "  " if i % 5 == 0 else f"Sub {i % 6}",
                "Grade Code": f"G{i % 7}",
                "COUNTRY": "India" if i % 3 else "USA",
                "Location": "Pune",
                "Division": "Div",
                "Department": f"Dept {i % 9}",
                "Email": f"e{i}@example.test",
                "ReportingManagerName": "Manager",
                "ReportingManagerCode": "M1",
                "EmploymentType": "Permanent",
                "Business Vertical": "Life Sciences" if i % 2 else "NULL",
            })
        if i % 97 == 1:  # duplicated HR code: the engine drops both
            hr.append(dict(hr[-1]))
        for m in months:
            if rnd.random() < 0.25:
                continue
            for j in range(rows_per_emp_month):
                rid += 1
                project = f"P{rnd.randrange(projects):04d}"
                day = 15 if (i % 211 == 3 and j == 0) else 1
                pt.append({
                    "row_id": f"R{rid:08d}" if rid % 101 else f" r{rid:08d}",
                    "project_id": project if rid % 53 else f" {project} ",
                    "proposal_number": 1 + rid % 3,
                    "sub_project_name": None if j == 0 else "Phase 2",
                    "employee_id": f" {code.lower()}" if rid % 17 == 0 else code,
                    "month_key": date(m // 100, m % 100, day),
                    "effort": float(rnd.choice([0, 20, 40, 80, 88, 176])) if rid % 89 else None,
                    "effort_value": None,
                    "is_override": False if rid % 61 else None,
                    "contract_type": rnd.choice(CONTRACTS),
                    "start_date": date(2025, 1 + rid % 12, 1),
                    "end_date": date(2027, 1 + rid % 12, 28),
                    "project_name": f"Project {project}" if rid % 7 else "null",
                    "parent_account_name": f"Client {int(project[1:]) % 40}" if rid % 5 else None,
                    "account_name": "Account X",
                    "bdu_name": "BDU 1" if rid % 4 else "  ",
                    "project_status": "Confirmed" if rid % 9 else "Pipeline",
                    "project_lead_name": "Lead",
                    "notes": None if rid % 3 else f"Note {rid}",
                    "employee_name": (code if rid % 23 == 0 else f"Employee {i}") if rid % 19 else None,
                    "primary_capability": CAPS[(i + m) % 4] if rid % 6 else None,
                    "secondary_capability": "Sub PT",
                    "department": f"Dept {i % 9}",
                    "grade": None if rid % 10 == 0 else f"G{i % 7}",
                    "location": "Pune",
                    "country": "India",
                })
                if rid % 401 == 0:  # conflicting duplicate in the same group
                    dup = dict(pt[-1])
                    rid += 1
                    dup["row_id"] = f"R{rid:08d}"
                    dup["effort"] = 10.0
                    pt.append(dup)
    for r in pt:
        r["effort_value"] = r.pop("effort")
    return pt, hr


# --------------------------------------------------------------------------- reference: full rows
def full_row_snapshot(pt, hr):
    """What azure_raw builds: every PT row, cleaned, through engine.build_snapshot."""
    pt_rows = [{
        "row_id": clean(r["row_id"]), "project_id": clean(r["project_id"]),
        "proposal_number": r["proposal_number"], "sub_project_name": r["sub_project_name"],
        "employee_key": employee_key(r["employee_id"]), "employee_code": clean(r["employee_id"]),
        "month_key": r["month_key"], "effort": r["effort_value"], "is_override": r["is_override"],
        "contract_type": clean(r["contract_type"]), "project_name": clean(r["project_name"]),
        "parent_account": clean(r["parent_account_name"]), "account": clean(r["account_name"]),
        "bdu": clean(r["bdu_name"]), "project_status": clean(r["project_status"]),
        "project_lead": clean(r["project_lead_name"]), "notes": clean(r["notes"]),
        "start_date": r["start_date"], "end_date": r["end_date"],
        "employee_name": clean(r["employee_name"]), "primary_capability": clean(r["primary_capability"]),
        "secondary_capability": clean(r["secondary_capability"]), "department": clean(r["department"]),
        "grade": clean(r["grade"]), "location": clean(r["location"]), "country": clean(r["country"]),
    } for r in pt]
    return e.build_snapshot(pt_rows, [st.shape_hr_row(r) for r in hr], TODAY)


# --------------------------------------------------------------------------- the six SQL results
def sql_results(pt, hr):
    """Python rendering of what each source_tables query returns."""
    start, after = st.window_bounds(TODAY)
    in_win = [r for r in pt if r["month_key"] is not None and start <= r["month_key"] < after]
    window_rows = [{
        k: r[k] for k in ("row_id", "project_id", "proposal_number", "sub_project_name", "employee_id",
                          "month_key", "is_override", "contract_type", "start_date", "end_date")
    } | {"effort": r["effort_value"]} for r in in_win if r["employee_id"] is not None]
    months = [{"month_int": m} for m in {e.month_int(r["month_key"]) for r in in_win}]

    # EMPLOYEE_LOOKUP
    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in pt:
        k = employee_key(r["employee_id"])
        if k:
            by_key[k].append(r)
    lookup = []
    for k, group in by_key.items():
        def is_real(r, k=k):
            n = clean(r["employee_name"])
            return n is not None and n.upper() != k
        group = sorted(group, key=lambda r: (
            not is_real(r), r["month_key"] is None, -e.month_int(r["month_key"]),
            clean(r["row_id"]) is None, clean(r["row_id"]) or ""))
        row = {"employee_code": min(clean(r["employee_id"]) for r in group)}
        for attr in ("employee_name", "primary_capability", "secondary_capability",
                     "department", "grade", "location", "country"):
            row[attr] = next((clean(r[attr]) for r in group if is_real(r) and clean(r[attr])), None)
        lookup.append(row)

    # PROJECT_DIMENSION + PROJECT_CONTRACT_TYPES
    by_pid: dict[str, list[dict]] = defaultdict(list)
    for r in pt:
        pid = clean(r["project_id"])
        if pid:
            by_pid[pid].append(r)
    cols = {"project_name": "project_name", "parent_account": "parent_account_name",
            "account": "account_name", "bdu": "bdu_name", "project_status": "project_status",
            "project_lead": "project_lead_name", "notes": "notes"}
    projects, types = [], set()
    for pid, group in by_pid.items():
        group = sorted(group, key=lambda r: (clean(r["row_id"]) is None, clean(r["row_id"]) or ""))
        row = {"project_id": pid}
        for name, col in cols.items():
            row[name] = next((clean(r[col]) for r in group if clean(r[col])), None)
        starts = [r["start_date"] for r in group if r["start_date"]]
        ends = [r["end_date"] for r in group if r["end_date"]]
        row["start_date"], row["end_date"] = (min(starts) if starts else None), (max(ends) if ends else None)
        projects.append(row)
        types |= {(pid, clean(r["contract_type"])) for r in group if clean(r["contract_type"])}
    contract_types = [{"project_id": p, "contract_type": t} for p, t in types]

    return {"window_rows": window_rows, "months": months, "lookup": lookup, "projects": projects,
            "contract_types": contract_types, "hr": hr}


# --------------------------------------------------------------------------- tests
@pytest.fixture(scope="module")
def data():
    pt, hr = synthetic_sources(employees=400, projects=60)
    return pt, hr, full_row_snapshot(pt, hr), st.snapshot_from_results(sql_results(pt, hr), TODAY)


def test_employees_match_full_row_engine(data):
    _, _, full, parts = data
    assert set(parts.employees) == set(full.employees)
    for key, emp in full.employees.items():
        assert parts.employees[key] == emp, key


def test_employee_months_and_quality_match(data):
    _, _, full, parts = data
    assert parts.window == full.window
    assert parts.employee_months == full.employee_months
    assert parts.data_quality == full.data_quality
    assert parts.months_with_data == full.months_with_data & set(full.window)
    assert full.data_quality["unresolved_rows"] > 0 and full.data_quality["missing_hr_match_employees"] > 0


def test_projects_match(data):
    _, _, full, parts = data
    assert parts.projects == full.projects
    assert any(p.contract_type == "Multiple contract types" for p in parts.projects.values())


def test_window_allocations_match(data):
    _, _, full, parts = data

    def strip(rows):
        return sorted((r.row_id or "", r.employee_key, r.month, r.status, r.reason, r.effort) for r in rows)

    in_window = set(full.window)
    assert strip(parts.rows) == strip(r for r in full.rows if r.named and r.month in in_window)
    assert {k: strip(v) for k, v in parts.rows_by_employee().items()} == {
        k: strip(v) for k, v in full.rows_by_employee().items()
    }


def test_sql_reads_only_the_two_source_tables():
    queries = [st.WINDOW_ROWS, st.MONTHS_WITH_DATA, st.EMPLOYEE_LOOKUP, st.PROJECT_DIMENSION,
               st.PROJECT_CONTRACT_TYPES, st.HR_EMPLOYEES, st.FINGERPRINT]
    for sql in queries:
        assert "dbo.rv_" not in sql and "rv2_" not in sql and "vw_" not in sql
        assert set(re.findall(r"dbo\.\w+", sql)) <= {
            "dbo.project_track_proposals_table", "dbo.zinghr_employee_master"}
        assert re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|EXEC)\b", sql, re.I) is None
    # detail rows are range-filtered on the plain month_key column (index friendly)
    assert "WHERE month_key >= ? AND month_key < ?" in st.WINDOW_ROWS


def test_cleanup_rules():
    assert clean("  Pharma  ") == "Pharma"
    assert clean(" NULL ") is None and clean("") is None and clean(None) is None
    assert clean(123) == "123"
    assert employee_key(" e00042 ") == "E00042"
    assert employee_key("null") is None


def test_reload_only_when_fingerprint_changes(monkeypatch):
    calls = {"load": 0}
    fp = {"value": (10, 1, 5, 2)}

    def fake_load(today, capacity):
        calls["load"] += 1
        pt, hr = synthetic_sources(employees=20, projects=5)
        return st.snapshot_from_results(sql_results(pt, hr), TODAY)

    monkeypatch.setattr(rv_service, "data_source", lambda: "source_tables")
    monkeypatch.setattr(st, "load_snapshot", fake_load)
    monkeypatch.setattr(st, "read_fingerprint", lambda: fp["value"])
    saved = dict(rv_service._state)  # noqa: SLF001
    rv_service._state.update(snapshot=None, fingerprint=None, checked=0.0, loaded=0.0, day=None)  # noqa: SLF001
    try:
        rv_service.get_snapshot()
        assert calls["load"] == 1
        rv_service.get_snapshot(fresh=True)  # same fingerprint: nothing reloaded
        assert calls["load"] == 1
        fp["value"] = (11, 3, 5, 2)  # a PT row was added
        rv_service.get_snapshot(fresh=True)
        assert calls["load"] == 2
        assert rv_service.data_info()["load_seconds"] >= 0
    finally:
        rv_service._state.clear()  # noqa: SLF001
        rv_service._state.update(saved)  # noqa: SLF001


def test_persistence_defaults_to_memory_for_source_tables(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("STAFFING_PERSISTENCE", raising=False)
    monkeypatch.delenv("RV_DATA_MODE", raising=False)
    s = Settings(_env_file=None, RV_DATA_SOURCE="source_tables")
    assert s.resolved_rv_data_source() == "source_tables"
    assert s.resolved_staffing_persistence() == "memory"
    assert Settings(_env_file=None, RV_DATA_SOURCE="azure").resolved_staffing_persistence() == "azure"


def test_assembly_speed_at_scale():
    """Python side of a reload at a large synthetic size (database time not included)."""
    pt, hr = synthetic_sources(employees=6000, projects=900, rows_per_emp_month=2)
    results = sql_results(pt, hr)
    started = time.perf_counter()
    snap = st.snapshot_from_results(results, TODAY)
    seconds = time.perf_counter() - started
    print(f"\nwindow rows={len(results['window_rows']):,} employees={len(snap.employees):,} "
          f"employee-months={len(snap.employee_months):,} assembly={seconds:.2f}s")
    assert seconds < 15
