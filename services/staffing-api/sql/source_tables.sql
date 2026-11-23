-- Canonical read-only sources for Resource Vision Confirmed Staffing (Azure SQL).
-- Python mirrors these queries in app/rv/sql.py and app/rv/skills_sql.py.
-- Availability math also uses precomputed dbo.rv2_* (refreshed from PT + ZingHR via dbo.rv2_Refresh).

-- ---------------------------------------------------------------------------
-- 1) Project Track allocations (dbo.project_track_proposals_table)
-- ---------------------------------------------------------------------------
-- Used for: project hours, employee-month allocations, org attributes on rows,
--           clients, project metadata. Normalised via dbo.rv_* helpers in-app.

/*
SELECT
    row_id                = dbo.rv_Blank(row_id),
    project_id            = dbo.rv_Blank(project_id),
    ...
FROM dbo.project_track_proposals_table
*/
-- Full query: app/rv/sql.py → PROJECT_TRACK_ROWS

-- ---------------------------------------------------------------------------
-- 2) ZingHR employee master (dbo.zinghr_employee_master)
-- ---------------------------------------------------------------------------
-- Used for: identity, joining/exit, HR match, organisation, business vertical.

/*
SELECT
    employee_key          = dbo.rv_Key(EmployeeCode),
    employee_code         = dbo.rv_Clean(EmployeeCode),
    ...
FROM dbo.zinghr_employee_master
*/
-- Full query: app/rv/sql.py → HR_EMPLOYEES

-- ---------------------------------------------------------------------------
-- 3) Skills dashboard view (dbo.vw_RV_EmployeeSkillsForDashboard)
-- ---------------------------------------------------------------------------
-- Used for: skill name/level per employee (pool ticks, dashboard filters).
-- Not joined to allocation rows in SQL; matched in Python on EmployeeCode.

SELECT
    employee_code = EmployeeCode,
    skill_name    = SkillName,
    skill_level   = CurrentSkillLevel
FROM dbo.vw_RV_EmployeeSkillsForDashboard;

-- ---------------------------------------------------------------------------
-- Optional: direct engine path (RV_DATA_SOURCE=azure_raw)
-- ---------------------------------------------------------------------------
-- Same PROJECT_TRACK_ROWS + HR_EMPLOYEES; engine.build_snapshot() in Python.

-- Default production path (RV_DATA_SOURCE=azure):
-- Read dbo.rv2_* facts populated by dbo.rv2_Refresh from the two base tables above.