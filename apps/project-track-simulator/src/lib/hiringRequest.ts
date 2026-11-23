import type { LaunchPayload } from "./launch";

export type HiringRequestSubmit = {
  project_id: string;
  capability: string;
  headcount: number;
  justification: string;
  start_date?: string;
  end_date?: string;
  position_id?: string;
  filters?: Record<string, string[]>;
  required_skills?: { name: string; level: string }[];
  month_hours?: { month_key: string; hours: number }[];
  pool_outcome?: { employees_shown: number; employees_total?: number };
  source?: string;
  bu_lead_cc?: string;
  project_lead_name?: string;
  project_lead_email?: string;
};

const FILTER_LABELS: Record<string, string> = {
  primary_capability: "Primary capability",
  secondary_capability: "Secondary capability",
  department: "Department",
  location: "Location",
  country: "Country",
  grade: "Grade",
};

export function defaultHiringCapability(filters?: Record<string, string[]>): string {
  return (
    filters?.primary_capability?.[0]?.trim() ||
    filters?.secondary_capability?.[0]?.trim() ||
    "General"
  );
}

export function hiringFilterSummary(filters?: Record<string, string[]>): { label: string; value: string }[] {
  const f = filters ?? {};
  return Object.entries(FILTER_LABELS).flatMap(([key, label]) => {
    const vals = f[key]?.filter(Boolean);
    if (!vals?.length) return [];
    return [{ label, value: vals.join(", ") }];
  });
}

export function buildHiringRequestFromPool(params: {
  launch: LaunchPayload;
  requiredSkills: { name: string; level: string }[];
  employeesShown: number;
  employeesTotal?: number;
}): HiringRequestSubmit {
  const { launch, requiredSkills, employeesShown, employeesTotal } = params;
  return {
    project_id: launch.project_id,
    capability: defaultHiringCapability(launch.filters),
    headcount: 1,
    justification:
      "No suitable employee in the internal Resource Vision pool for this role profile. Requesting external staffing via MyNextHire.",
    start_date: launch.start_date,
    end_date: launch.end_date,
    position_id: launch.role_id,
    filters: launch.filters ?? {},
    required_skills: requiredSkills.filter((s) => s.name.trim()),
    month_hours: launch.month_hours ?? [],
    pool_outcome: { employees_shown: employeesShown, employees_total: employeesTotal },
    source: "resource_vision_empty_pool",
  };
}