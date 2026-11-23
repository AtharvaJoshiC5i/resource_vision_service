import type { CandidateStatus } from "../api/staffing";

export type SelectionAction = "direct" | "kb" | "interview";

const ACTION_LABEL: Record<SelectionAction, string> = {
  direct: "Direct select",
  kb: "KB / training",
  interview: "Interview",
};

export function selectionActionLabel(action: SelectionAction | string): string {
  return ACTION_LABEL[action as SelectionAction] ?? action;
}

/** Best-effort route label from workflow status when the action is not stored on the row. */
export function inferSelectionPath(status: CandidateStatus): string | null {
  if (status === "Interview Pending" || status === "Interview Booked" || status === "Expired") {
    return ACTION_LABEL.interview;
  }
  if (status === "KB Pending" || status === "Training" || status === "Training Failed/Delayed") {
    return ACTION_LABEL.kb;
  }
  if (status === "Skills Matched" || status === "Reserved" || status === "Confirmed") {
    return ACTION_LABEL.direct;
  }
  return null;
}