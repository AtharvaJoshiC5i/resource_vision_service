import { useMemo, useState } from "react";
import { AlertCircle, ArrowLeft } from "lucide-react";

import { buttonClass, primaryButtonClass } from "../../components/ui/primitives";
import { TableScroll } from "../../components/ui/TableCard";
import { tableHeadClass } from "../../components/ui/tableClasses";

import {
  applyFillEmptyMonths,
  buildInitialGrid,
  countEmptyHourCells,
  hoursPlanForApi,
  monthColumnsFromLaunch,
  validateHoursGrid,
  type MonthColumn,
} from "./allocationHoursUtils";
import type { PoolEmployee } from "./types";

const ACTION_COPY = {
  direct: { title: "Direct select", confirm: "Confirm and reserve" },
  kb: { title: "Send to Knowledge Benchmarking", confirm: "Send to KB" },
  interview: { title: "Book interview", confirm: "Book interview" },
} as const;

export type AllocationCommitPlan = {
  employee_key: string;
  months: { month_key: string; hours: number }[];
};

export function AllocationHoursStep({
  action,
  employeeKeys,
  pool,
  monthHours,
  capacityHours,
  working,
  serverError,
  onBack,
  onConfirm,
  savedMonths,
}: {
  action: "direct" | "kb" | "interview";
  employeeKeys: string[];
  pool: PoolEmployee[];
  monthHours: { month_key: string; hours: number }[];
  capacityHours: number;
  working?: boolean;
  serverError?: string | null;
  onBack: () => void;
  onConfirm: (plans: AllocationCommitPlan[]) => void;
  savedMonths?: { month_key: string; hours: number }[];
}) {
  const columns = useMemo(() => monthColumnsFromLaunch(monthHours), [monthHours]);
  const selected = useMemo(
    () =>
      employeeKeys
        .map((k) => pool.find((e) => e.employee_key.toUpperCase() === k.toUpperCase()))
        .filter(Boolean) as PoolEmployee[],
    [employeeKeys, pool],
  );

  const [grid, setGrid] = useState(() => buildInitialGrid(employeeKeys, pool, columns, savedMonths));
  const [error, setError] = useState<string | null>(null);
  /** Latest hours value the user committed in any month cell; drives the optional auto-fill prompt. */
  const [suggestedFillHours, setSuggestedFillHours] = useState<number | null>(null);

  const copy = ACTION_COPY[action];
  const emptyCells = useMemo(
    () => countEmptyHourCells(employeeKeys, pool, columns, grid),
    [employeeKeys, pool, columns, grid],
  );
  const showFillPrompt = suggestedFillHours != null && suggestedFillHours > 0 && emptyCells > 0;

  const updateCell = (employeeKey: string, monthIndex: number, raw: string) => {
    const n = raw === "" ? 0 : Number(raw);
    setGrid((prev) => {
      const row = [...(prev[employeeKey] ?? columns.map(() => 0))];
      row[monthIndex] = Number.isFinite(n) ? Math.max(0, n) : 0;
      return { ...prev, [employeeKey]: row };
    });
    setError(null);
  };

  const commitHourEntry = (hours: number) => {
    if (Number.isFinite(hours) && hours > 0) {
      setSuggestedFillHours(hours);
    }
  };

  const fillEmptyMonths = () => {
    if (suggestedFillHours == null || suggestedFillHours <= 0) return;
    setGrid((prev) => applyFillEmptyMonths(employeeKeys, pool, columns, prev, suggestedFillHours));
    setError(null);
  };

  const submit = () => {
    const msg = validateHoursGrid(employeeKeys, pool, columns, grid, capacityHours);
    if (msg) {
      setError(msg);
      return;
    }
    const plans: AllocationCommitPlan[] = employeeKeys.map((key) => ({
      employee_key: key,
      months: hoursPlanForApi(columns, grid[key] ?? []),
    }));
    onConfirm(plans);
  };

  if (!columns.length) {
    return (
      <div className="px-4 py-6 text-sm text-muted">
        The project has no months to staff. Check its start and end dates.
        <button type="button" className={`${buttonClass} mt-3`} onClick={onBack}>
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 space-y-2.5 border-b border-hairline bg-surface px-5 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ink">{copy.title}</h3>
            <p className="text-xs text-muted">Enter hours per month. Entries above the free hours are blocked.</p>
          </div>
          <button type="button" className={buttonClass} onClick={onBack} disabled={working}>
            <ArrowLeft size={14} aria-hidden />
            Back
          </button>
        </div>
        {error || serverError ? (
          <div
            role="alert"
            className="flex gap-2 rounded-lg border border-error bg-[var(--color-error-soft)] px-3 py-2 text-xs text-error-ink"
          >
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden />
            <p>{error ?? serverError}</p>
          </div>
        ) : null}
        {showFillPrompt ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-hairline bg-canvas px-3 py-2 text-xs text-ink">
            <span>
              Fill <span className="font-medium tabular-nums">{emptyCells}</span> empty month
              {emptyCells === 1 ? "" : "s"} with{" "}
              <span className="font-semibold tabular-nums">{suggestedFillHours}h</span> each?
            </span>
            <button
              type="button"
              className={primaryButtonClass}
              disabled={working}
              onClick={fillEmptyMonths}
            >
              Apply to empty months
            </button>
            <span className="text-muted">Already-filled months are left unchanged.</span>
          </div>
        ) : null}
      </div>

      <TableScroll label="Monthly hours by employee" className="min-h-0 flex-1 px-2 sm:px-3">
        <table className="rv-table rv-table--matrix min-w-full text-xs">
          <thead>
            <tr>
              <th className={[tableHeadClass, "sticky left-0 z-[1] bg-surface text-left"].join(" ")}>Employee</th>
              {columns.map((col) => (
                <th key={col.iso} className={[tableHeadClass, "min-w-[5.25rem] text-center"].join(" ")}>
                  {col.label}
                  {col.demand > 0 ? (
                    <span className="mt-0.5 block text-[0.625rem] font-normal text-muted">demand {col.demand}h</span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {selected.map((emp) => (
              <tr key={emp.employee_key}>
                <th
                  scope="row"
                  className="sticky left-0 z-[1] bg-surface px-2 py-2 text-left font-medium text-ink align-top"
                >
                  <div className="max-w-[9rem] truncate" title={emp.employee_name}>
                    {emp.employee_name}
                  </div>
                  <div className="text-[0.6875rem] font-normal text-muted tabular-nums">{emp.employee_code}</div>
                </th>
                {columns.map((col, i) => (
                  <MonthInputCell
                    key={col.iso}
                    col={col}
                    value={grid[emp.employee_key]?.[i] ?? 0}
                    bookable={emp.months[i]?.bookable_hours ?? 0}
                    disabled={working}
                    onChange={(v) => updateCell(emp.employee_key, i, v)}
                    onValueCommitted={commitHourEntry}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>

      <footer className="shrink-0 border-t border-hairline bg-surface px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-auto text-xs text-muted">
            {working ? "Processing" : `${selected.length} selected · ${capacityHours} h monthly capacity`}
          </span>
          <button type="button" className={buttonClass} onClick={onBack} disabled={working}>
            Cancel
          </button>
          <button type="button" className={primaryButtonClass} onClick={submit} disabled={working}>
            {copy.confirm}
          </button>
        </div>
      </footer>
    </div>
  );
}

function MonthInputCell({
  col,
  value,
  bookable,
  disabled,
  onChange,
  onValueCommitted,
}: {
  col: MonthColumn;
  value: number;
  bookable: number;
  disabled?: boolean;
  onChange: (raw: string) => void;
  onValueCommitted: (hours: number) => void;
}) {
  const over = value > bookable + 1e-6;

  const commit = (raw: string) => {
    if (raw === "") return;
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) onValueCommitted(n);
  };

  return (
    <td className="px-1 py-2 text-center align-top">
      <input
        type="number"
        min={0}
        step={1}
        disabled={disabled}
        aria-label={`Hours for ${col.label}`}
        className={[
          "rv-field mx-auto h-8 w-[4.25rem] rounded-md px-1 text-center text-xs tabular-nums",
          over ? "ring-2 ring-error" : "",
        ].join(" ")}
        value={value === 0 ? "" : value}
        placeholder="0"
        onChange={(e) => onChange(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commit((e.target as HTMLInputElement).value);
          }
        }}
      />
      <p className={`mt-1 text-[0.625rem] tabular-nums ${bookable <= 0 ? "text-muted" : "text-success-ink"}`}>
        {Math.floor(bookable)} h free
      </p>
    </td>
  );
}