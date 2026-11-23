export type { LaunchPayload, PoolsSelectionResult } from "../../lib/launch";

export type PoolMonthCell = {
  month_key: number;
  label: string;
  status: string;
  remaining: number | null;
  bookable_hours: number;
};

export type EmployeeBlockHolder = {
  actor_id: string;
  actor_display_name: string;
  project_id: string;
  candidate_status?: string | null;
  interview_booked?: boolean;
  interview_booked_at?: string | null;
};

export type PoolEmployee = {
  employee_key: string;
  employee_code: string;
  employee_name: string;
  bench_class: string;
  primary_capability?: string | null;
  secondary_capability?: string | null;
  department?: string | null;
  grade?: string | null;
  location?: string | null;
  country?: string | null;
  skills?: { name: string; level: string }[];
  skill_ticks: { skill: string; required_level?: string; current_level?: string | null; matched: boolean; ranked?: boolean }[];
  months: PoolMonthCell[];
  interview_leads_count: number;
  in_flight_status?: string | null;
  block_slots_max?: number;
  block_slots_active?: number;
  block_slots_remaining?: number;
  can_block?: boolean;
  active_blocks?: EmployeeBlockHolder[];
};

export type PoolSearchMeta = {
  count: number;
  project_months: number[];
  capacity_hours?: number;
};