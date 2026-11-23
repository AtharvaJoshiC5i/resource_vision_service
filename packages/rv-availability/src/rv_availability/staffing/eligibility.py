from __future__ import annotations

from rv_availability import engine as e


def eligibility_result(
    emp: e.Employee,
    project_months: list[int],
    *,
    contract_eligibility_implemented: bool = False,
) -> dict:
    reasons: list[str] = []
    if not emp.hr_matched:
        reasons.append("Missing HR match")
    if not emp.dates_valid:
        reasons.append("Invalid HR dates")
    for m in project_months:
        if not employed_in_month(emp, m):
            reasons.append(f"Not employed in month {m}")
    leaver = (emp.employee_status or "").casefold()
    if "fnf" in leaver or leaver.startswith("reliev"):
        reasons.append("Leaver status")
    contract_note = None
    if not contract_eligibility_implemented:
        contract_note = "unimplemented"
    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "contract_eligibility": contract_note,
    }


def employed_in_month(emp: e.Employee, month: int) -> bool:
    if emp.joining is None:
        return False
    if emp.joining > e.month_end(month):
        return False
    return emp.exit is None or emp.exit >= e.month_start(month)