import type { Candidate, CandidateStatus } from "../../api/staffing";
import { Trash2 } from "lucide-react";
import { buttonClass, primaryButtonClass, quietButtonClass } from "../../components/ui/primitives";
import { FINISHED } from "../../lib/candidateStatus";

export type CandidateHandlers = {
  busy: string | null;
  onFinalCheck: (c: Candidate) => void;
  onRelease: (c: Candidate) => void;
  onInterviewResults: (c: Candidate) => void;
  onBookInterview: (c: Candidate) => void;
  onDirectSelect: (c: Candidate) => void;
  onRetryKb: (c: Candidate) => void;
};

export function CandidateActions({ c, h }: { c: Candidate; h: CandidateHandlers }) {
  const disabled = h.busy === c.id;
  const status: CandidateStatus = c.status;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {status === "Interview Booked" ? (
        <button type="button" className={primaryButtonClass} disabled={disabled} onClick={() => h.onInterviewResults(c)}>
          Interview results
        </button>
      ) : null}
      {status === "KB Pending" ? (
        <button type="button" className={buttonClass} disabled={disabled} onClick={() => h.onRetryKb(c)}>
          Retry KB request
        </button>
      ) : null}
      {status === "Skills Matched" ? (
        <>
          <button type="button" className={buttonClass} disabled={disabled} onClick={() => h.onBookInterview(c)}>
            Book interview
          </button>
          <button type="button" className={primaryButtonClass} disabled={disabled} onClick={() => h.onDirectSelect(c)}>
            Direct select
          </button>
        </>
      ) : null}
      {status === "Reserved" ? (
        <button type="button" className={primaryButtonClass} disabled={disabled} onClick={() => h.onFinalCheck(c)}>
          Retry PT write
        </button>
      ) : null}
      {!FINISHED.has(status) ? (
        <button type="button" className={quietButtonClass} disabled={disabled} onClick={() => h.onRelease(c)}>
          <Trash2 size={13} aria-hidden /> Release
        </button>
      ) : null}
    </div>
  );
}