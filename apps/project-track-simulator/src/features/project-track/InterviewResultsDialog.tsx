import { useEffect, useState } from "react";
import { UserCheck } from "lucide-react";

import { SelectField, buttonClass, fieldClass, labelClass, primaryButtonClass } from "../../components/ui/primitives";
import { useDialogFocus } from "../../hooks/useDialogFocus";

export type InterviewResultsChoice =
  | { outcome: "pass" }
  | { outcome: "reject"; rejectionType: "Technical" | "Non-technical"; reason: string };

export function InterviewResultsDialog({
  employeeName,
  employeeCode,
  busy,
  onCancel,
  onSubmit,
}: {
  employeeName: string;
  employeeCode?: string;
  busy?: boolean;
  onCancel: () => void;
  onSubmit: (choice: InterviewResultsChoice) => void;
}) {
  const ref = useDialogFocus(true);
  const [rejectionType, setRejectionType] = useState<"Technical" | "Non-technical">("Technical");
  const [reason, setReason] = useState("");

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const rejectValid = reason.trim().length > 0;

  return (
    <div
      className="rv-backdrop fixed inset-0 z-[60] flex items-center justify-center bg-[color-mix(in_srgb,var(--color-ink)_42%,transparent)] p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="interview-results-title"
        tabIndex={-1}
        className="rv-dialog rv-frame w-full max-w-md rounded-xl bg-surface shadow-[var(--shadow-elevated)]"
        onKeyDown={(e) => e.key === "Escape" && !busy && onCancel()}
      >
        <header className="rv-rule-b px-4 py-3">
          <p className="rv-eyebrow text-[0.625rem]">Interview results</p>
          <h2 id="interview-results-title" className="text-base font-semibold text-ink">
            {employeeName}
          </h2>
          {employeeCode ? (
            <p className="text-xs tabular-nums text-muted">{employeeCode}</p>
          ) : null}
        </header>

        <div className="space-y-4 bg-canvas px-4 py-4">
          <section className="rv-inset-panel rounded-lg p-3">
            <p className="text-xs leading-5 text-muted">
              If the interview went well, confirm the employee on this project. When monthly hours are already on record
              (for example after Knowledge Benchmarking), allocation runs immediately; otherwise you can confirm or adjust
              hours in the next step.
            </p>
            <button
              type="button"
              className={`${primaryButtonClass} mt-3 w-full sm:w-auto`}
              disabled={busy}
              onClick={() => onSubmit({ outcome: "pass" })}
            >
              <UserCheck size={16} aria-hidden />
              Select employee
            </button>
          </section>

          <div className="flex items-center gap-2 text-[0.625rem] font-medium uppercase tracking-wide text-muted">
            <span className="h-px flex-1 bg-hairline" aria-hidden />
            or reject
            <span className="h-px flex-1 bg-hairline" aria-hidden />
          </div>

          <section>
            <p className="mb-2 text-xs text-muted">
              Rejections are listed under <strong className="font-medium text-ink-soft">Previously rejected candidates</strong>.
              Technical rejections are also sent to Knowledge Benchmarking; non-technical rejections are recorded on the
              project only.
            </p>
            <label className="block">
              <span className={labelClass}>Rejection type</span>
              <SelectField
                value={rejectionType}
                disabled={busy}
                onChange={(e) => setRejectionType(e.target.value as "Technical" | "Non-technical")}
              >
                <option value="Technical">Technical</option>
                <option value="Non-technical">Non-technical</option>
              </SelectField>
            </label>
            <label className="mt-3 block">
              <span className={labelClass}>Interview feedback / rejection reason</span>
              <textarea
                className={`${fieldClass} h-24 py-2`}
                placeholder="Required when rejecting the candidate"
                value={reason}
                disabled={busy}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
          </section>
        </div>

        <footer className="rv-rule-t flex flex-wrap justify-end gap-2 px-4 py-3">
          <button type="button" className={buttonClass} onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className={buttonClass}
            disabled={!rejectValid || busy}
            onClick={() =>
              onSubmit({
                outcome: "reject",
                rejectionType,
                reason: reason.trim(),
              })
            }
          >
            Reject candidate
          </button>
        </footer>
      </div>
    </div>
  );
}