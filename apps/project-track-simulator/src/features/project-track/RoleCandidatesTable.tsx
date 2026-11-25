import type { Candidate } from "../../api/staffing";
import { tableHeadClass } from "../../components/ui/tableClasses";
import { hours } from "../../lib/format";
import type { ResourceRole } from "../../lib/launch";

import { CandidateStatusPill } from "./CandidateStatus";
import { CandidateActions, type CandidateHandlers } from "./CandidateActions";
import { criterionValue, monthLabel, resolveMonthColumns, roleCriteriaColumns } from "./roleRowShared";

function hoursForMonth(c: Candidate, monthKey: string): number {
  const found = c.months.find((m) => m.month_key === monthKey);
  return found?.hours ?? 0;
}

export function RoleCandidatesTable({
  candidates,
  handlers,
  roleFor,
  monthKeys = [],
}: {
  candidates: Candidate[];
  handlers: CandidateHandlers;
  roleFor: (candidate: Candidate) => ResourceRole;
  monthKeys?: string[];
}) {
  const monthCols = resolveMonthColumns(monthKeys, candidates);

  return (
    <div className="rv-role-candidates rv-inset-panel overflow-hidden rounded-lg">
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
                Employee
              </th>
              {monthCols.map((mk) => (
                <th
                  key={mk}
                  scope="col"
                  className={[tableHeadClass, "rv-role-cand-hd", "rv-role-cand-hd--month", "text-center min-w-[3.5rem]"].join(" ")}
                >
                  {monthLabel(mk)}
                  <span className="mt-0.5 block text-[0.625rem] font-normal normal-case text-muted">Hours</span>
                </th>
              ))}
              <th scope="col" className={[tableHeadClass, "rv-role-cand-hd", "text-left min-w-[9rem]"].join(" ")}>
                Next steps
              </th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const role = roleFor(c);
              return (
                <tr key={c.id} className="rv-role-candidate-row border-b border-hairline last:border-0">
                  <td className="rv-role-cand-cell align-top px-2 py-2">
                    <CandidateStatusPill status={c.status} />
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
                      title={criterionValue(String(role[col.key] ?? ""))}
                    >
                      {criterionValue(String(role[col.key] ?? ""))}
                    </td>
                  ))}
                  <th scope="row" className="rv-role-cand-cell rv-role-cand-emp align-top px-2 py-2 text-left font-medium text-ink">
                    <div className="max-w-[12rem] truncate" title={c.employee_name}>
                      {c.employee_name}
                    </div>
                    <div className="font-normal tabular-nums text-muted">{c.employee_code}</div>
                  </th>
                  {monthCols.map((mk) => {
                    const h = hoursForMonth(c, mk);
                    return (
                      <td
                        key={mk}
                        className="rv-role-cand-cell rv-role-cand-month align-top px-1.5 py-2 text-center tabular-nums"
                      >
                        <span
                          className={[
                            "rv-role-cand-hours",
                            h > 0 ? "rv-role-cand-hours--set" : "rv-role-cand-hours--empty",
                          ].join(" ")}
                          title={h > 0 ? `${hours(h)} planned` : "No hours entered"}
                        >
                          {h > 0 ? hours(h) : "—"}
                        </span>
                      </td>
                    );
                  })}
                  <td className="rv-role-cand-cell align-top px-2 py-2">
                    <CandidateActions c={c} h={handlers} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}