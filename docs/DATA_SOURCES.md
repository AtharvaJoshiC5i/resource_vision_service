# Data sources for Confirmed Staffing

## Azure SQL objects (read-only)

| Object | Role |
|--------|------|
| **`dbo.project_track_proposals_table`** | Project Track allocations (~7k rows). Hours, projects, clients, row-level org attributes. |
| **`dbo.zinghr_employee_master`** | ZingHR HR master (~117 employees). Identity, dates, status, org, business vertical. |
| **`dbo.vw_RV_EmployeeSkillsForDashboard`** | Skills per employee (name + current level). Pool green/red ticks and dashboard skill filters. |

**SQL:** [`services/staffing-api/sql/source_tables.sql`](../services/staffing-api/sql/source_tables.sql) (reference) and Python queries in `app/rv/sql.py`, `app/rv/skills_sql.py`.

## How the API uses them

| `RV_DATA_MODE` / `RV_DATA_SOURCE` | Availability | Skills (pools + `/api/rv`) |
|-----------------------------------|--------------|----------------------------|
| **`azure`** (default) | Precomputed **`dbo.rv2_*`** (refreshed from PT + ZingHR via `dbo.rv2_Refresh`) | **`vw_RV_EmployeeSkillsForDashboard`** |
| **`azure_raw`** | Recomputes from **`project_track_proposals_table` + `zinghr_employee_master`** each cache cycle | Same skills view |
| **`demo`** | Synthetic data in memory | Stub skills (tests only) |

When not in `demo`, `get_ports()` wires **`AzureSkillsProvider`** and **`AzureProjectTrackRead`** so pool search and final-check hit the real tables above (skills via the view; PT/ZingHR via `PROJECT_TRACK_ROWS` / `HR_EMPLOYEES`).

## Other

| Source | Status |
|--------|--------|
| **`dbo.rv_staffing_*`** | Staffing workflow (reservations, candidates) when `STAFFING_PERSISTENCE=azure` |
| Knowledge Benchmarking / MyNextHire | Stub ports until Phase 5 adapters |

Engine rules: [`packages/rv-availability/docs/CALCULATION_SPEC.md`](../packages/rv-availability/docs/CALCULATION_SPEC.md).