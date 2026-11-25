# Resource Vision Confirmed Staffing Service

Single **Azure SQL** database hosts Project Track, ZingHR, `rv2_*` facts, skills view, and `dbo.rv_staffing_*` workflow tables.

## Backend (`services/staffing-api`)

Mirrors [`resource_vision_poc`](c:\Programming and Coding\resource_vision_poc) availability:

- `app/database.py` — pyodbc to Azure SQL
- `app/rv/service.py` — cached `rv2_*` snapshot (`RV_DATA_SOURCE=azure`)
- `app/rv/facts.py`, `sql.py`, `routes.py`, `skills.py` — same read API at `/api/rv/*`
- `app/staffing_store.py` — `dbo.rv_staffing_*` via pyodbc (`STAFFING_PERSISTENCE=azure`)

Copy `services/staffing-api/.env.example` to `.env` locally with Azure settings. **Do not commit secrets.**

**Data switch** (restart API after change):

| `RV_DATA_MODE` | Behaviour |
|----------------|-----------|
| `azure` | `rv2_*` / PT / ZingHR from Azure SQL; use `STAFFING_PERSISTENCE=azure` for workflow tables |
| `source_tables` | Reads **only** `dbo.project_track_proposals_table` and `dbo.zinghr_employee_master`. No `dbo.rv_*` helper functions, views, `rv2_*` tables or staffing tables needed; staffing store defaults to `memory` |
| `demo` | Synthetic availability; staffing store forced to `memory` |

Optional override: `RV_DATA_SOURCE` if `RV_DATA_MODE` is unset. Check active mode: `GET /api/staffing/runtime`.

### Running on another database with only the two source tables

Set in `.env`: your own `AZURE_SQL_CONNECTION_STRING`, `RV_DATA_MODE=source_tables`, and leave
`STAFFING_PERSISTENCE` unset (workflow state is then kept in memory and lost on restart). The tables
must have the same column names as the current Project Track and ZingHR tables.

How it stays fast (`app/rv/source_tables.py`):

- detail rows are read only for the 19-month window (`month_key` range filter);
- the employee name lookup and the project dimension, which need every month, are reduced to one row
  per employee / project inside SQL;
- the six reads run in parallel; requests are served from the in-memory snapshot;
- a one-row change fingerprint (row counts + checksums) is checked every `RV_SOURCE_CHECK_SECONDS`
  (default 60) in the background, and before every confirmation. The snapshot reloads only when it
  changes, or after `RV_SOURCE_MAX_AGE_SECONDS` (default 900).

Text cleanup is done in Python (`clean` / `employee_key`: trim, blank or `null` -> empty, codes in upper
case). If your `dbo.rv_Blank` / `rv_Clean` / `rv_Key` rules differ, change them in that one file.
Skills still come from `dbo.vw_RV_EmployeeSkillsForDashboard`; without that view the skill columns are empty.

Optional, if the first load is slow on a very large table (needs DBA approval, creates an index):
`CREATE INDEX IX_ptp_month_key ON dbo.project_track_proposals_table (month_key);`

Apply service DDL once: [`services/staffing-api/sql/staffing_schema.sql`](services/staffing-api/sql/staffing_schema.sql).

```powershell
pip install -e ./packages/rv-availability
pip install -r ./services/staffing-api/requirements.txt
cd services/staffing-api
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Unit tests use `RV_DATA_SOURCE=demo` and `STAFFING_PERSISTENCE=memory` (see `tests/conftest.py`).

## UI (`apps/project-track-simulator`)

Single React page: **Project Track** (Project details, Knowledge Benchmarking, Audit & MNH tabs) + **Resource Vision Pools** (modal). Availability logic lives in the API (`/api/rv/*`); the POC's other pages are intentionally not replicated. Uses the POC design system ([`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md)).

```powershell
cd apps/project-track-simulator
npm install
npm run dev
```

Dev server: http://127.0.0.1:5175 — proxies `/api` to the staffing API on port 8010.

## Design reference

[`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) is copied from the POC and governs all UI work.