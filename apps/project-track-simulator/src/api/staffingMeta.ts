/** Shape returned by `GET /api/staffing/meta` (availability_options keys). */
export type StaffingMetaOptions = {
  capabilities?: string[];
  secondary_capabilities?: string[];
  departments?: string[];
  locations?: string[];
  countries?: string[];
  grades?: string[];
};

export type ProjectTrackFilterOptions = {
  primary_capability: string[];
  secondary_capability: string[];
  department: string[];
  location: string[];
  country: string[];
  grade: string[];
};

export function filterOptionsFromStaffingMeta(data: { options?: StaffingMetaOptions }): ProjectTrackFilterOptions {
  const o = data.options ?? {};
  return {
    primary_capability: o.capabilities ?? [],
    secondary_capability: o.secondary_capabilities ?? [],
    department: o.departments ?? [],
    location: o.locations ?? [],
    country: o.countries ?? [],
    grade: o.grades ?? [],
  };
}