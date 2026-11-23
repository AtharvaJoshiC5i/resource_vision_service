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
| `demo` | Synthetic availability; staffing store forced to `memory` |

Optional override: `RV_DATA_SOURCE` if `RV_DATA_MODE` is unset. Check active mode: `GET /api/staffing/runtime`.

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