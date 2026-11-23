import type { AvailabilityStatus } from "../../api/types";
import { Pill, StatusChip, primaryButtonClass, quietButtonClass } from "../../components/ui/primitives";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassPool, tableHeadClass, tableStickyColClass } from "../../components/ui/tableClasses";
import { hours } from "../../lib/format";
import { STATUS_ORDER } from "../../lib/status";

import { PoolSkillsCell } from "./PoolSkillsCell";
import type { PoolEmployee } from "./types";

function isAvailabilityStatus(value: string): value is AvailabilityStatus {
  return (STATUS_ORDER as string[]).includes(value);
}

function MonthStatusMark({ status }: { status: string }) {
  if (isAvailabilityStatus(status)) {
    return (
      <span className="rv-pool-month__mark-slot" aria-hidden>
        <StatusChip status={status} size="sm" />
      </span>
    );
  }
  const title = status?.trim() || "No record";
  const glyph = title === "No record" ? "—" : title.length === 1 ? title : title.slice(0, 1).toUpperCase();
  return (
    <span className="rv-pool-month__mark rv-pool-month__mark--empty" title={title} aria-label={title}>
      {glyph}
    </span>
  );
}

function MonthCell({ cell }: { cell: PoolEmployee["months"][number] }) {
  return (
    <div className="rv-pool-month">
      <MonthStatusMark status={cell.status} />
      <span className="rv-pool-month__hrs">{hours(cell.bookable_hours)}</span>
    </div>
  );
}

function BenchBadge({ bench }: { bench: string }) {
  const tone =
    bench === "True Bench" ? "rv-pool-bench--true" : bench === "Future Bench" ? "rv-pool-bench--future" : "";
  return <span className={["rv-pool-bench", tone].filter(Boolean).join(" ")}>{bench}</span>;
}

export function PoolEmployeeTable({
  rows,
  monthLabels,
  selected,
  loading,
  stats,
  onToggle,
  onToggleAll,
  onSelectTop,
  onClearSelection,
  onRequestHiring,
}: {
  rows: PoolEmployee[];
  monthLabels: string[];
  selected: Set<string>;
  loading?: boolean;
  stats?: { bench: number; full: number };
  onToggle: (key: string, on: boolean) => void;
  onToggleAll: (keys: string[]) => void;
  onSelectTop?: () => void;
  onClearSelection?: () => void;
  onRequestHiring?: () => void;
}) {
  const canSelect = (r: PoolEmployee) => (r.can_block ?? true) && !r.in_flight_status;
  const allKeys = rows.filter(canSelect).map((r) => r.employee_key);
  const allSelected = allKeys.length > 0 && allKeys.every((k) => selected.has(k));

  const meta =
    stats != null
      ? `${stats.bench} true bench · ${stats.full} full skill match · Cells show bookable hours`
      : "Cells show bookable hours per month";

  return (
    <TableCard
      className="rv-pool-table-card flex min-h-0 flex-1 flex-col"
      titleId="pool-candidates-title"
      title="Recommended resources"
      count={loading ? "…" : rows.length}
      description={meta}
      actions={
        <>
          {onSelectTop ? (
            <button type="button" className={quietButtonClass} onClick={onSelectTop}>
              Select top 5
            </button>
          ) : null}
          {onClearSelection ? (
            <button type="button" className={quietButtonClass} onClick={onClearSelection}>
              Clear
            </button>
          ) : null}
        </>
      }
    >
      <TableScroll label="Ranked employee pool" className="rv-pool-table-scroll min-h-0 flex-1 max-h-full">
        <table className={tableClassPool}>
          <thead>
            <tr>
              <th className={[tableHeadClass, "rv-pool-col-check"].join(" ")}>
                <input
                  type="checkbox"
                  className="rv-pool-check"
                  aria-label="Select all"
                  checked={allSelected}
                  onChange={(e) => onToggleAll(e.target.checked ? allKeys : [])}
                />
              </th>
              <th className={[tableHeadClass, tableStickyColClass, "rv-pool-col-emp"].join(" ")}>Employee</th>
              <th className={[tableHeadClass, "rv-pool-col-skills"].join(" ")}>Skills</th>
              <th className={[tableHeadClass, "rv-pool-col-bench"].join(" ")}>Bench</th>
              <th className={[tableHeadClass, "rv-pool-col-grade"].join(" ")}>Grade</th>
              {monthLabels.map((label) => (
                <th key={label} className={[tableHeadClass, "rv-pool-col-month", "text-center"].join(" ")}>
                  <span className="rv-table-head-stack">
                    <span className="rv-table-head-stack__primary">{label}</span>
                  </span>
                </th>
              ))}
              <th className={[tableHeadClass, "rv-pool-col-num", "text-center"].join(" ")}>Blocks</th>
              <th className={[tableHeadClass, "rv-pool-col-num", "text-center"].join(" ")}>Intv.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.employee_key}>
                <td className="rv-pool-col-check">
                  <input
                    type="checkbox"
                    className="rv-pool-check"
                    checked={selected.has(row.employee_key)}
                    disabled={!canSelect(row)}
                    onChange={(e) => onToggle(row.employee_key, e.target.checked)}
                    aria-label={`Select ${row.employee_name}`}
                  />
                </td>
                <th scope="row" className={[tableStickyColClass, "rv-pool-emp"].join(" ")}>
                  <div className="rv-pool-emp__name">{row.employee_name}</div>
                  <div className="rv-pool-emp__meta">
                    <span className="tabular-nums">{row.employee_code}</span>
                    {row.secondary_capability ? <span>{row.secondary_capability}</span> : null}
                  </div>
                  {row.in_flight_status ? (
                    <Pill fg="var(--color-primary)" wrap>
                      {row.in_flight_status}
                    </Pill>
                  ) : null}
                  {(row.block_slots_active ?? 0) > 0 ? (
                    <div className={`rv-pool-blocks ${row.can_block === false ? "rv-pool-blocks--full" : ""}`}>
                      <div className="rv-pool-blocks__title">
                        {row.block_slots_active}/{row.block_slots_max ?? 3} lead blocks
                      </div>
                      <ul className="rv-pool-blocks__list">
                        {(row.active_blocks ?? []).map((b) => (
                          <li key={`${b.project_id}-${b.actor_id}`} title={b.project_id}>
                            {b.actor_display_name}
                            {b.interview_booked ? <span className="rv-pool-blocks__tag">iv</span> : null}
                          </li>
                        ))}
                      </ul>
                      {row.can_block === false ? (
                        <p className="rv-pool-blocks__warn">No slots left</p>
                      ) : null}
                    </div>
                  ) : null}
                </th>
                <td className="rv-pool-col-skills align-top">
                  <PoolSkillsCell row={row} />
                </td>
                <td className="rv-pool-col-bench align-middle">
                  <BenchBadge bench={row.bench_class} />
                </td>
                <td className="rv-pool-col-grade align-middle tabular-nums">{row.grade ?? "–"}</td>
                {row.months.map((cell) => (
                  <td key={cell.month_key} className="rv-pool-col-month align-middle text-center">
                    <MonthCell cell={cell} />
                  </td>
                ))}
                <td className="rv-pool-col-num align-middle text-center tabular-nums text-ink-soft">
                  {row.block_slots_active ?? 0}
                  {row.block_slots_max != null ? `/${row.block_slots_max}` : ""}
                </td>
                <td className="rv-pool-col-num align-middle text-center tabular-nums text-ink-soft">
                  {row.interview_leads_count || "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !loading ? (
          <div className="rv-pool-table-empty">
            <p className="rv-pool-table-empty__lead">No employees match the current filters.</p>
            <p className="rv-pool-table-empty__hint">
              Request staffing through MyNextHire with this project&apos;s role profile, skills, and timeline. You choose
              how many resources are needed.
            </p>
            {onRequestHiring ? (
              <button type="button" className={primaryButtonClass} onClick={onRequestHiring}>
                Send request to MyNextHire
              </button>
            ) : null}
          </div>
        ) : null}
      </TableScroll>
    </TableCard>
  );
}