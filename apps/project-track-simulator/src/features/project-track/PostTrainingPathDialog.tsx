import { ClipboardList, UserCheck } from "lucide-react";

import { buttonClass, primaryButtonClass } from "../../components/ui/primitives";
import { useDialogFocus } from "../../hooks/useDialogFocus";

export function PostTrainingPathDialog({
  employeeName,
  onCancel,
  onInterview,
  onDirectSelect,
  busy,
}: {
  employeeName: string;
  onCancel: () => void;
  onInterview: () => void;
  onDirectSelect: () => void;
  busy?: boolean;
}) {
  const ref = useDialogFocus(true);

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
        aria-labelledby="post-training-title"
        tabIndex={-1}
        className="rv-dialog rv-frame w-full max-w-md rounded-xl bg-surface shadow-[var(--shadow-elevated)]"
        onKeyDown={(e) => e.key === "Escape" && !busy && onCancel()}
      >
        <header className="rv-rule-b px-4 py-3">
          <p className="rv-eyebrow text-[0.625rem]">Training completed</p>
          <h2 id="post-training-title" className="text-base font-semibold text-ink">
            Next step for {employeeName}
          </h2>
          <p className="mt-1 text-xs leading-5 text-muted">
            Choose how to proceed on this project: book an interview (same interview workflow as pool selection) or
            direct select with monthly hours and final capacity check.
          </p>
        </header>
        <div className="flex flex-col gap-2 px-4 py-4">
          <button type="button" className={buttonClass} disabled={busy} onClick={onInterview}>
            <ClipboardList size={16} aria-hidden />
            Book for interview
          </button>
          <button type="button" className={primaryButtonClass} disabled={busy} onClick={onDirectSelect}>
            <UserCheck size={16} aria-hidden />
            Direct select (enter hours)
          </button>
        </div>
        <footer className="rv-rule-t flex justify-end px-4 py-3">
          <button type="button" className={buttonClass} onClick={onCancel} disabled={busy}>
            Decide later
          </button>
        </footer>
      </div>
    </div>
  );
}