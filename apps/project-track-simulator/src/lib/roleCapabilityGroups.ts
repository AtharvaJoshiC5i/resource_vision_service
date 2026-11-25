import type { Candidate, MnhStaffingSlot } from "../api/staffing";

import { FINISHED } from "./candidateStatus";
import type { ResourceRole } from "./launch";

type Filters = Record<string, string[] | string> | null | undefined;

function first(filters: Filters, key: string): string {
  const raw = filters?.[key];
  return (Array.isArray(raw) ? (raw[0] ?? "") : (raw ?? "")).trim();
}

/**
 * Section key: primary + secondary capability only, ignoring case and surrounding spaces. Other
 * filters never affect it. Same rule as the staffing API (`app/services/capability_group.py`).
 */
export function sectionKeyFromFilters(filters: Filters): string {
  return `${first(filters, "primary_capability").toLowerCase()}|${first(filters, "secondary_capability").toLowerCase()}`;
}

export function sectionKeyForRole(role: Pick<ResourceRole, "primary" | "secondary">): string {
  return `${role.primary.trim().toLowerCase()}|${role.secondary.trim().toLowerCase()}`;
}

export function sectionLabel(primary: string, secondary: string): string {
  return `${primary.trim() || "Any"} · ${secondary.trim() || "Any"}`;
}

/** Position id sent with a selection: readable, and the same for every selection in a section. */
export function positionIdForRole(role: Pick<ResourceRole, "primary" | "secondary">): string {
  return `${role.primary.trim() || "Any"} / ${role.secondary.trim() || "Any"}`;
}

export function blankRole(): ResourceRole {
  return {
    id: "",
    primary: "",
    secondary: "",
    department: "",
    location: "",
    country: "",
    grade: "",
    skills: [],
    monthHours: [],
    status: "Open",
  };
}

/** The filters a selection was made with, as a role (criteria columns, relaunching the pool). */
export function roleFromFilters(
  filters: Filters,
  id: string | null | undefined,
  skills: { name: string; level: string }[] = [],
): ResourceRole {
  const role: ResourceRole = {
    ...blankRole(),
    primary: first(filters, "primary_capability"),
    secondary: first(filters, "secondary_capability"),
    department: first(filters, "department"),
    location: first(filters, "location"),
    country: first(filters, "country"),
    grade: first(filters, "grade"),
    skills,
  };
  return { ...role, id: id || positionIdForRole(role) };
}

export type CapabilitySection = {
  key: string;
  label: string;
  candidates: Candidate[];
  mnhSlots: MnhStaffingSlot[];
};

/**
 * Live selections grouped into one section per primary + secondary pair, in the order the pairs
 * were first used. Within a section, people are listed in the order they were selected.
 */
export function buildSections(candidates: Candidate[], mnhSlots: MnhStaffingSlot[]): CapabilitySection[] {
  const sections = new Map<string, CapabilitySection>();
  const sectionFor = (key: string, filters: Filters) => {
    let s = sections.get(key);
    if (!s) {
      s = {
        key,
        label: sectionLabel(first(filters, "primary_capability"), first(filters, "secondary_capability")),
        candidates: [],
        mnhSlots: [],
      };
      sections.set(key, s);
    }
    return s;
  };
  for (const c of candidates) {
    if (FINISHED.has(c.status)) continue;
    sectionFor(c.capability_group_key ?? sectionKeyFromFilters(c.demand_filters), c.demand_filters).candidates.push(c);
  }
  for (const slot of mnhSlots) {
    if (slot.status !== "Hiring from MNH") continue;
    sectionFor(slot.capability_group_key ?? sectionKeyFromFilters(slot.demand_filters), slot.demand_filters).mnhSlots.push(slot);
  }
  return [...sections.values()];
}
