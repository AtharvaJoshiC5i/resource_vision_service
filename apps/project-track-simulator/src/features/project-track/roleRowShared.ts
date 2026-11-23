import type { Candidate } from "../../api/staffing";
import type { ResourceRole } from "../../lib/launch";

export const roleCriteriaColumns: { key: keyof ResourceRole; label: string }[] = [
  { key: "primary", label: "Primary" },
  { key: "secondary", label: "Secondary" },
  { key: "department", label: "Department" },
  { key: "location", label: "Location" },
  { key: "country", label: "Country" },
  { key: "grade", label: "Grade" },
];

export function criterionValue(raw: string | undefined): string {
  const t = (raw ?? "").trim();
  return t || "Any";
}

export function monthLabel(monthKey: string): string {
  const d = new Date(`${monthKey.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return monthKey.slice(0, 7);
  return d.toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" });
}

export function resolveMonthColumns(monthKeys: string[], candidates: Candidate[]): string[] {
  if (monthKeys.length) return monthKeys;
  const keys = new Set<string>();
  for (const c of candidates) {
    for (const m of c.months) keys.add(m.month_key);
  }
  return [...keys].sort((a, b) => a.localeCompare(b));
}