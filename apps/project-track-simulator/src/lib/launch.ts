export type ResourceRole = {
  id: string;
  primary: string;
  secondary: string;
  department: string;
  location: string;
  country: string;
  grade: string;
  skills: { name: string; level: string }[];
  monthHours: { month_key: string; hours: number }[];
  status: string;
  employeeLabel?: string;
};

export type LaunchPayload = {
  project_id: string;
  start_date: string;
  end_date: string;
  role_id?: string;
  filters?: Record<string, string[]>;
  required_skills?: { name: string; level: string }[];
  month_hours?: { month_key: string; hours: number }[];
  launch_token?: string;
  callback_origin?: string;
};

export type PoolsSelectionResult =
  | { status: "cancelled" }
  | {
      status: "completed";
      demand_id: string;
      employee_keys: string[];
      action: string;
      reservations: string[];
      role_id?: string;
      skills?: { name: string; level: string }[];
      results: { employee_key: string; ok: boolean; status?: string; message?: string }[];
      /** Shown on Project Track when PT / availability write is stubbed or completed. */
      availability_notice?: string;
    };

export const DEV_LAUNCH_TOKEN = "dev-simulator-token";

const FILTER_KEYS = [
  "primary_capability",
  "secondary_capability",
  "department",
  "location",
  "country",
  "grade",
] as const;

/** PT launch filters with empty values removed. When every role row is “Any”, returns undefined. */
export function stripLaunchFilters(filters?: Record<string, string[]>): Record<string, string[]> | undefined {
  if (!filters) return undefined;
  const out: Record<string, string[]> = {};
  for (const key of FILTER_KEYS) {
    const vals = (filters[key] ?? []).map((s) => s.trim()).filter(Boolean);
    if (vals.length) out[key] = vals;
  }
  return Object.keys(out).length ? out : undefined;
}

export function launchHasRoleFilters(filters?: Record<string, string[]>): boolean {
  return Boolean(stripLaunchFilters(filters));
}

export function roleToLaunch(
  projectId: string,
  startDate: string,
  endDate: string,
  role: ResourceRole,
  origin: string,
): LaunchPayload {
  const filters: Record<string, string[]> = {};
  if (role.primary) filters.primary_capability = [role.primary];
  if (role.secondary) filters.secondary_capability = [role.secondary];
  if (role.department) filters.department = [role.department];
  if (role.location) filters.location = [role.location];
  if (role.country) filters.country = [role.country];
  if (role.grade) filters.grade = [role.grade];

  return {
    project_id: projectId,
    start_date: startDate,
    end_date: endDate,
    role_id: role.id,
    filters: Object.keys(filters).length ? filters : undefined,
    required_skills: role.skills.filter((s) => s.name.trim()),
    month_hours: role.monthHours,
    launch_token: DEV_LAUNCH_TOKEN,
    callback_origin: origin,
  };
}

export function defaultMonthHours(startIso: string, count = 6, hoursEach = 40): { month_key: string; hours: number }[] {
  const base = new Date(startIso.slice(0, 10));
  const out: { month_key: string; hours: number }[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(base);
    d.setUTCMonth(d.getUTCMonth() + i);
    const mk = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
    out.push({ month_key: mk, hours: hoursEach });
  }
  return out;
}