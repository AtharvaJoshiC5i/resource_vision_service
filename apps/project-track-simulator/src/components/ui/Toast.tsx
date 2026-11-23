import { useEffect } from "react";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";

export type ToastTone = "info" | "success" | "error";

export type ToastMessage = { id: number; text: string; tone: ToastTone };

const ICON = { info: Info, success: CircleCheck, error: CircleAlert } as const;

/** Bottom-right notification; dismisses itself after a few seconds (errors stay longer). */
export function Toast({ toast, onDismiss }: { toast: ToastMessage | null; onDismiss: () => void }) {
  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(onDismiss, toast.tone === "error" ? 12000 : 6000);
    return () => window.clearTimeout(id);
  }, [toast, onDismiss]);

  if (!toast) return null;
  const Icon = ICON[toast.tone];
  return (
    <div className="rv-toast-region" role="status" aria-live="polite">
      <div key={toast.id} className={`rv-toast rv-toast--${toast.tone}`}>
        <Icon aria-hidden className="rv-toast__icon" />
        <p className="rv-toast__text">{toast.text}</p>
        <button type="button" className="rv-toast__close" aria-label="Dismiss" onClick={onDismiss}>
          <X aria-hidden className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
