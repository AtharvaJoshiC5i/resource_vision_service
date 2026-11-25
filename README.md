# Resource Vision Confirmed Staffing Service

Commands are for Windows PowerShell and start from the repository root unless stated.

## Prerequisites

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+
- Microsoft ODBC Driver 18 for SQL Server
- A database login that can read the source tables, with your IP allowed in the Azure SQL firewall

## Backend

### First-time setup

```powershell
python -m venv venv
```

```powershell
.\venv\Scripts\Activate.ps1
```

```powershell
cd services\staffing-api
```

```powershell
pip install -r requirements.txt
```

```powershell
Copy-Item .env.example .env
```

Run `pip install` from `services\staffing-api`; it fails from any other folder.

Edit `services\staffing-api\.env` and set these lines (never commit this file):

```
RV_DATA_MODE=source_tables
STAFFING_PERSISTENCE=memory
AZURE_SQL_CONNECTION_STRING=Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<database>;Uid=<user>;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;
```

`source_tables` reads `dbo.project_track_proposals_table` and `dbo.zinghr_employee_master`. Skills come from
`dbo.vw_RV_EmployeeSkillsForDashboard`; without it the skill columns are empty. With `memory`, staffing
selections are lost when the API restarts. To run without a database, set `RV_DATA_MODE=demo`.

### Start

From the repository root:

```powershell
.\venv\Scripts\Activate.ps1
```

```powershell
cd services\staffing-api
```

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Check it from a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/staffing/runtime
```

With `source_tables`, the API terminal also logs `Loaded availability from source tables in ...s` once the data
has loaded.

## Frontend

Start the backend first, then open a second terminal at the repository root:

```powershell
cd apps\project-track-simulator
```

```powershell
npm install
```

```powershell
npm run dev
```

Open http://localhost:5175. `npm install` is only needed the first time and after dependencies change.
