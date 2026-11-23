import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { LaunchPayload, PoolsSelectionResult } from "../../lib/launch";

import { ResourceVisionPoolsPanel, type PoolsWizardStep } from "./ResourceVisionPoolsPanel";

export function ResourceVisionPoolsModal({
  launch,
  onClose,
  onComplete,
  onMnhRecorded,
}: {
  launch: LaunchPayload;
  onClose: () => void;
  onComplete: (result: PoolsSelectionResult) => void;
  onMnhRecorded?: (slotCount: number, roleId?: string) => void;
}) {
  const dialogRef = useDialogFocus(true);
  const [wizardStep, setWizardStep] = useState<PoolsWizardStep>("pool");
  const title = wizardStep === "hours" ? "Assign monthly hours" : "Select employees";

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="rv-backdrop fixed inset-0 z-50 flex items-end justify-center bg-[color-mix(in_srgb,var(--color-ink)_48%,transparent)] p-0 sm:items-center sm:p-6"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="rv-pools-title"
        tabIndex={-1}
        className="rv-dialog rv-density flex h-[100dvh] w-full max-w-[88rem] flex-col overflow-hidden rounded-none border-0 bg-surface text-sm shadow-[var(--shadow-elevated)] sm:h-[min(92dvh,900px)] sm:max-h-[92dvh] sm:rounded-xl sm:border sm:border-hairline"
      >
        <header className="rv-pools-modal-header flex shrink-0 items-center justify-between gap-4 border-b border-hairline px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-medium text-muted">Resource vision</p>
            <h2 id="rv-pools-title" className="mt-0.5 text-lg font-semibold leading-snug text-ink">
              {title}
            </h2>
            <p className="rv-pools-modal-meta">
              <span className="rv-pools-modal-meta__chip">{launch.project_id}</span>
              <span className="rv-pools-modal-meta__chip tabular-nums">
                {launch.start_date} to {launch.end_date}
              </span>
            </p>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-canvas hover:text-ink"
            aria-label="Close"
            onClick={onClose}
          >
            <X size={18} aria-hidden />
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col bg-canvas">
          <ResourceVisionPoolsPanel
            launch={launch}
            onCancel={onClose}
            onComplete={onComplete}
            onMnhRecorded={onMnhRecorded}
            onStepChange={setWizardStep}
          />
        </div>
      </div>
    </div>
  );
}