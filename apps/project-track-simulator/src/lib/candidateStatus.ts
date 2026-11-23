import type { CandidateStatus } from "../api/staffing";

/** Statuses that no longer take part in the workflow. */
export const FINISHED: ReadonlySet<CandidateStatus> = new Set(["Released", "Rejected", "Expired"]);

/** Role-level status: the furthest-along live candidate, or Open. */
const PRIORITY: CandidateStatus[] = [
  "Confirmed",
  "Reserved",
  "Skills Matched",
  "Interview Booked",
  "Training",
  "KB Pending",
  "Interview Pending",
  "Training Failed/Delayed",
  "New",
];

export function roleStatus(statuses: CandidateStatus[]): CandidateStatus | "Open" {
  for (const s of PRIORITY) if (statuses.includes(s)) return s;
  return "Open";
}

/** Role row status when MNH placeholders exist but no in-flight internal candidates. */
export function roleStatusForRole(
  candidateStatuses: CandidateStatus[],
  hasMnhSlots: boolean,
): CandidateStatus | "Open" | "Hiring from MNH" {
  const base = roleStatus(candidateStatuses);
  if (base !== "Open") return base;
  if (hasMnhSlots) return "Hiring from MNH";
  return "Open";
}

export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime())
    ? "–"
    : d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
