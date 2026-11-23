import type { CandidateStatus } from "../../api/staffing";
import { Pill } from "../../components/ui/primitives";

const COLOR: Record<CandidateStatus, string> = {
  New: "var(--color-muted)",
  "Skills Matched": "var(--color-primary)",
  "KB Pending": "var(--color-warning)",
  Training: "var(--color-warning)",
  "Training Failed/Delayed": "var(--color-error)",
  "Interview Pending": "var(--color-warning)",
  "Interview Booked": "var(--color-primary)",
  Expired: "var(--color-muted)",
  Rejected: "var(--color-error)",
  Reserved: "var(--color-primary)",
  Confirmed: "var(--color-success)",
  Released: "var(--color-muted)",
};

export function CandidateStatusPill({ status }: { status: CandidateStatus | "Hiring from MNH" | "Open" }) {
  if (status === "Hiring from MNH") {
    return <Pill fg="var(--color-warning)">Hiring from MNH</Pill>;
  }
  if (status === "Open") {
    return <span className="rv-chip">Open</span>;
  }
  return <Pill fg={COLOR[status] ?? "var(--color-muted)"}>{status}</Pill>;
}
