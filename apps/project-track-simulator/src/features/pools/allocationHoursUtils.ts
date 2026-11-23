import type { PoolEmployee } from "./types";

export type MonthColumn = {
  iso: string;
  label: string;
  demand: number;
};

export function monthColumnsFromLaunch(monthHours: { month_key: string; hours: number }[] | undefined): MonthColumn[] {
  return (monthHours ?? []).map((m) => ({
    iso: m.month_key,
    label: m.month_key.slice(0, 7),
    demand: m.hours,
  }));
}

export function initialHoursRow(emp: PoolEmployee, columns: MonthColumn[]): number[] {
  return columns.map((col, i) => {
    const avail = emp.months[i]?.bookable_hours ?? 0;
    const demand = col.demand ?? 0;
    if (avail <= 0) return 0;
    return Math.min(Math.max(0, demand), avail);
  });
}

function monthKeyPrefix(iso: string): string {
  return iso.slice(0, 7);
}

export function buildInitialGrid(
  employeeKeys: string[],
  pool: PoolEmployee[],
  columns: MonthColumn[],
  savedMonths?: { month_key: string; hours: number }[],
): Record<string, number[]> {
  const grid: Record<string, number[]> = {};
  const savedByMonth = new Map(
    (savedMonths ?? []).map((m) => [monthKeyPrefix(m.month_key), m.hours] as const),
  );
  for (const key of employeeKeys) {
    const emp = pool.find((e) => e.employee_key.toUpperCase() === key.toUpperCase());
    if (!emp) continue;
    const base = initialHoursRow(emp, columns);
    grid[key] = columns.map((col, i) => {
      const saved = savedByMonth.get(monthKeyPrefix(col.iso));
      if (saved != null && saved > 0) return saved;
      return base[i] ?? 0;
    });
  }
  return grid;
}

export function validateHoursGrid(
  employeeKeys: string[],
  pool: PoolEmployee[],
  columns: MonthColumn[],
  grid: Record<string, number[]>,
  capacityHours: number,
): string | null {
  for (const key of employeeKeys) {
    const emp = pool.find((e) => e.employee_key === key);
    if (!emp) return "Selected employee is no longer in the pool. Go back and refresh.";
    const row = grid[key] ?? [];
    const total = row.reduce((n, h) => n + (Number.isFinite(h) ? h : 0), 0);
    if (total <= 0) {
      return `${emp.employee_name}: enter hours greater than zero in at least one month.`;
    }
    for (let i = 0; i < columns.length; i++) {
      const h = Number(row[i] ?? 0);
      const avail = emp.months[i]?.bookable_hours ?? 0;
      const label = columns[i]?.label ?? `month ${i + 1}`;
      if (!Number.isFinite(h) || h < 0) {
        return `${emp.employee_name}: invalid hours for ${label}.`;
      }
      if (h > capacityHours + 1e-6) {
        return `${emp.employee_name}: ${label} exceeds the ${capacityHours}h monthly capacity cap.`;
      }
      if (h > avail + 1e-6) {
        return `${emp.employee_name}: ${label} needs ${h}h but only ${Math.floor(avail)}h is bookable. Lower the effort or pick another month.`;
      }
    }
  }
  return null;
}

export function hoursPlanForApi(
  columns: MonthColumn[],
  row: number[],
): { month_key: string; hours: number }[] {
  return columns
    .map((col, i) => ({ month_key: col.iso, hours: Math.max(0, Number(row[i] ?? 0)) }))
    .filter((m) => m.hours > 0);
}

/** Month cell is empty when hours are zero (user has not entered a value). */
export function countEmptyHourCells(
  employeeKeys: string[],
  pool: PoolEmployee[],
  columns: MonthColumn[],
  grid: Record<string, number[]>,
): number {
  let n = 0;
  for (const key of employeeKeys) {
    const emp = pool.find((e) => e.employee_key === key);
    if (!emp) continue;
    const row = grid[key] ?? [];
    for (let i = 0; i < columns.length; i++) {
      if ((row[i] ?? 0) > 0) continue;
      if ((emp.months[i]?.bookable_hours ?? 0) <= 0) continue;
      n++;
    }
  }
  return n;
}

/** Fill only cells that are still empty (0h); never overwrite months the user already set. */
export function applyFillEmptyMonths(
  employeeKeys: string[],
  pool: PoolEmployee[],
  columns: MonthColumn[],
  grid: Record<string, number[]>,
  hours: number,
): Record<string, number[]> {
  if (!Number.isFinite(hours) || hours <= 0) return grid;
  const next: Record<string, number[]> = { ...grid };
  for (const key of employeeKeys) {
    const emp = pool.find((e) => e.employee_key === key);
    if (!emp) continue;
    const row = [...(next[key] ?? columns.map(() => 0))];
    for (let i = 0; i < columns.length; i++) {
      if ((row[i] ?? 0) > 0) continue;
      const avail = emp.months[i]?.bookable_hours ?? 0;
      if (avail <= 0) continue;
      row[i] = Math.min(hours, avail);
    }
    next[key] = row;
  }
  return next;
}