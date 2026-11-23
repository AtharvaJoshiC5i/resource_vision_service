import type { MnhStaffingSlot } from "../../api/staffing";
import { Pill } from "../../components/ui/primitives";
import { tableHeadClass } from "../../components/ui/tableClasses";
import type { ResourceRole } from "../../lib/launch";

import { roleCriteriaColumns, criterionValue, monthLabel, resolveMonthColumns } from "./roleRowShared";

export function RoleMnhSlotsTable({
  slots,
  role,
  monthKeys = [],
}: {
  slots: MnhStaffingSlot[];
  role: ResourceRole;
  monthKeys?: string[];
}) {
  const monthCols = resolveMonthColumns(monthKeys, []);

  return (
    <div className="rv-role-candidates rv-inset-panel rv-role-candidates--mnh mb-2 overflow-hidden rounded-lg">
      <p className="border-b border-hairline px-3 py-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-muted">
        Pending MyNextHire · {slots.length} {slots.length === 1 ? "position" : "positions"}
      </p>
      <div className="overflow-x-auto">
        <table className="rv-role-candidates-table min-w-full text-xs">
          <thead>
            <tr className="border-b border-hairline bg-canvas/60">
              <th scope="col" className={[tableHeadClass, "rv-role-cand-hd", "text-left min-w-[7rem]"].join(" ")}>
                Status
              </th>
              {roleCriteriaColumns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={[tableHeadClass, "rv-role-cand-hd", "text-left min-w-[6.25rem]"].join(" ")}
                >
                  {col.label}
                </th>
              ))}
              <th scope="col" className={[tableHeadClass, "rv-role-cand-hd", "text-left min-w-[9rem]"].join(" ")}>
                Resource
              </th>
              {monthCols.map((mk) => (
                <th
                  key={mk}
                  scope="col"
                  className={[tableHeadClass, "rv-role-cand-hd", "rv-role-cand-hd--month", "text-center min-w-[3.5rem]"].join(" ")}
                >
                  {monthLabel(mk)}
                </th>
              ))}
              <th scope="col" className={[tableHeadClass, "rv-role-cand-hd", "text-left min-w-[9rem]"].join(" ")}>
                Notes
              </th>
            </tr>
          </thead>
          <tbody>
            {slots.map((slot) => (
              <tr key={slot.id} className="rv-role-candidate-row rv-role-candidate-row--mnh border-b border-hairline last:border-0">
                <td className="rv-role-cand-cell align-top px-2 py-2">
                  <Pill fg="var(--color-warning)">{slot.status}</Pill>
                </td>
                {roleCriteriaColumns.map((col) => (
                  <td
                    key={col.key}
                    className={[
                      "rv-role-cand-cell",
                      "rv-role-cand-crit",
                      "align-top px-2 py-2",
                      criterionValue(String(role[col.key] ?? "")) === "Any" ? "rv-role-cand-crit--any" : "",
                    ].join(" ")}
                  >
                    {criterionValue(String(role[col.key] ?? ""))}
                  </td>
                ))}
                <th scope="row" className="rv-role-cand-cell rv-role-cand-emp align-top px-2 py-2 text-left font-medium text-ink">
                  <div>MyNextHire placeholder</div>
                  <div className="font-normal text-muted">
                    Slot {slot.slot_index} of {slot.headcount_total} · {slot.capability}
                  </div>
                </th>
                {monthCols.map((mk) => (
                  <td key={mk} className="rv-role-cand-cell rv-role-cand-month align-top px-1.5 py-2 text-center">
                    <span className="rv-role-cand-hours rv-role-cand-hours--empty">TBD</span>
                  </td>
                ))}
                <td className="rv-role-cand-cell align-top px-2 py-2 text-ink-soft">
                  HR staffing in progress; hours assigned when a hire is onboarded.
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}