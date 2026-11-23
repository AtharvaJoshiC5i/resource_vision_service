import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Send } from "lucide-react";

import { staffingApi } from "../../api/staffing";
import {
  buttonClass,
  fieldClass,
  labelClass,
  primaryButtonClass,
} from "../../components/ui/primitives";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { HiringRequestSubmit } from "../../lib/hiringRequest";
import { hiringFilterSummary } from "../../lib/hiringRequest";
import { buildMnhStaffingEmailLocal, type MnhEmailDraft } from "../../lib/mnhEmailTemplate";

import { MnhEmailPreview } from "./MnhEmailPreview";

type Step = "details" | "email";

export function MyNextHireRequestDialog({
  draft,
  busy,
  onCancel,
  onSubmit,
}: {
  draft: HiringRequestSubmit;
  busy?: boolean;
  onCancel: () => void;
  onSubmit: (body: HiringRequestSubmit) => Promise<MnhEmailDraft | null>;
}) {
  const ref = useDialogFocus(true);
  const [step, setStep] = useState<Step>("details");
  const [capability, setCapability] = useState(draft.capability);
  const [headcount, setHeadcount] = useState(draft.headcount);
  const [justification, setJustification] = useState(draft.justification);
  const [buLeadCc, setBuLeadCc] = useState("");
  const [projectLeadName, setProjectLeadName] = useState("");
  const [projectLeadEmail, setProjectLeadEmail] = useState("");
  const [defaults, setDefaults] = useState({ hrTo: "hr-staffing@mynexthire.example", buCc: "bu-lead@example.com" });
  const [emailDraft, setEmailDraft] = useState<MnhEmailDraft | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const roleRows = useMemo(() => hiringFilterSummary(draft.filters), [draft.filters]);
  const skills = draft.required_skills ?? [];
  const monthCount = draft.month_hours?.length ?? 0;

  const valid = capability.trim().length > 0 && headcount >= 1 && justification.trim().length > 0;

  const assembledRequest = useCallback((): HiringRequestSubmit => {
    return {
      ...draft,
      capability: capability.trim(),
      headcount: Math.max(1, Math.floor(headcount)),
      justification: justification.trim(),
      bu_lead_cc: buLeadCc.trim() || undefined,
      project_lead_name: projectLeadName.trim() || undefined,
      project_lead_email: projectLeadEmail.trim() || undefined,
    };
  }, [draft, capability, headcount, justification, buLeadCc, projectLeadName, projectLeadEmail]);

  useEffect(() => {
    let cancelled = false;
    staffingApi
      .mnhEmailDefaults()
      .then((d) => {
        if (!cancelled) {
          setDefaults({ hrTo: d.hr_to, buCc: d.bu_lead_cc });
          if (!buLeadCc) setBuLeadCc(d.bu_lead_cc);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- load defaults once

  const loadEmailPreview = async () => {
    if (!valid) return;
    setPreviewLoading(true);
    setPreviewError(null);
    const body = assembledRequest();
    try {
      const res = await staffingApi.previewHiringEmail(body);
      setEmailDraft(res.email_draft);
      setStep("email");
    } catch {
      setEmailDraft(buildMnhStaffingEmailLocal(body, defaults.hrTo, defaults.buCc));
      setStep("email");
      setPreviewError("Using offline email preview — API preview was unavailable.");
    } finally {
      setPreviewLoading(false);
    }
  };

  const confirmSubmit = async () => {
    setSubmitError(null);
    const body = assembledRequest();
    try {
      const draftFromApi = await onSubmit(body);
      const nextDraft = draftFromApi ?? emailDraft;
      if (nextDraft) {
        setEmailDraft({
          ...nextDraft,
          delivery_status: "mock_sent",
        });
      }
      setRecorded(true);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Could not record the MyNextHire request");
    }
  };

  return (
    <div
      className="rv-backdrop fixed inset-0 z-[70] flex items-center justify-center bg-[color-mix(in_srgb,var(--color-ink)_42%,transparent)] p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy && !previewLoading) onCancel();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="mnh-request-title"
        tabIndex={-1}
        className="rv-dialog rv-frame flex max-h-[min(90dvh,44rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-elevated)]"
        onKeyDown={(e) => e.key === "Escape" && !busy && !previewLoading && onCancel()}
      >
        <header className="rv-rule-b shrink-0 px-4 py-3">
          <p className="rv-eyebrow text-[0.625rem]">MyNextHire</p>
          <h2 id="mnh-request-title" className="text-base font-semibold text-ink">
            {step === "details" ? "Request external staffing" : "Email to HR"}
          </h2>
          <p className="mt-1 text-xs leading-5 text-muted">
            {step === "details"
              ? "Complete the request details. The next step shows the email that will go to HR, with the BU lead in Cc."
              : "Email delivery is not enabled yet — this is the message that will be sent when it is."}
          </p>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto bg-canvas px-4 py-4">
          {step === "details" ? (
            <>
              <section className="rv-inset-panel mb-4 rounded-lg p-3" aria-label="Project context">
                <h3 className="text-[0.625rem] font-semibold uppercase tracking-wide text-muted">Project</h3>
                <dl className="mt-2 space-y-1 text-xs">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted">Project ID</dt>
                    <dd className="font-medium text-ink">{draft.project_id}</dd>
                  </div>
                  {draft.position_id ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted">Resource role</dt>
                      <dd className="font-medium text-ink">{draft.position_id}</dd>
                    </div>
                  ) : null}
                  {draft.start_date && draft.end_date ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted">Timeline</dt>
                      <dd className="font-medium tabular-nums text-ink">
                        {draft.start_date.slice(0, 10)} → {draft.end_date.slice(0, 10)}
                        {monthCount ? ` · ${monthCount} month(s)` : ""}
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </section>

              {roleRows.length > 0 ? (
                <section className="mb-4" aria-label="Role filters">
                  <h3 className="mb-2 text-[0.625rem] font-semibold uppercase tracking-wide text-muted">Role criteria</h3>
                  <ul className="flex flex-wrap gap-1.5">
                    {roleRows.map((r) => (
                      <li key={r.label} className="rv-soft-tag">
                        <span className="text-muted">{r.label}:</span> {r.value}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {skills.length > 0 ? (
                <section className="mb-4" aria-label="Required skills">
                  <h3 className="mb-2 text-[0.625rem] font-semibold uppercase tracking-wide text-muted">Required skills</h3>
                  <ul className="flex flex-wrap gap-1.5">
                    {skills.map((s) => (
                      <li key={s.name} className="rv-soft-tag">
                        {s.name} · {s.level}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <form
                className="space-y-3 border-t border-hairline pt-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  void loadEmailPreview();
                }}
              >
                <label className="block">
                  <span className={labelClass}>Capability (for MNH)</span>
                  <input
                    className={fieldClass}
                    value={capability}
                    disabled={busy || previewLoading}
                    onChange={(e) => setCapability(e.target.value)}
                  />
                </label>
                <label className="block">
                  <span className={labelClass}>Headcount requested</span>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    className={fieldClass}
                    value={headcount}
                    disabled={busy || previewLoading}
                    onChange={(e) => setHeadcount(Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
                <label className="block">
                  <span className={labelClass}>Justification</span>
                  <textarea
                    className={`${fieldClass} min-h-[4.5rem] py-2`}
                    value={justification}
                    disabled={busy || previewLoading}
                    onChange={(e) => setJustification(e.target.value)}
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className={labelClass}>Your name (signature)</span>
                    <input
                      className={fieldClass}
                      value={projectLeadName}
                      disabled={busy || previewLoading}
                      onChange={(e) => setProjectLeadName(e.target.value)}
                      placeholder="Project lead name"
                    />
                  </label>
                  <label className="block">
                    <span className={labelClass}>Your email</span>
                    <input
                      type="email"
                      className={fieldClass}
                      value={projectLeadEmail}
                      disabled={busy || previewLoading}
                      onChange={(e) => setProjectLeadEmail(e.target.value)}
                      placeholder="name@company.com"
                    />
                  </label>
                </div>
                <label className="block">
                  <span className={labelClass}>BU lead (Cc)</span>
                  <input
                    type="email"
                    className={fieldClass}
                    value={buLeadCc}
                    disabled={busy || previewLoading}
                    onChange={(e) => setBuLeadCc(e.target.value)}
                    placeholder={defaults.buCc}
                  />
                  <span className="mt-1 block text-[0.6875rem] text-muted">
                    HR receives the request at <span className="font-medium text-ink-soft">{defaults.hrTo}</span>
                  </span>
                </label>
              </form>
            </>
          ) : emailDraft ? (
            <>
              {previewError ? <p className="mb-3 text-xs text-warning-ink">{previewError}</p> : null}
              {submitError ? (
                <p className="mb-3 text-xs text-error-ink" role="alert">
                  {submitError}
                </p>
              ) : null}
              <MnhEmailPreview draft={emailDraft} recorded={recorded} />
            </>
          ) : null}
        </div>

        <footer className="rv-rule-t flex shrink-0 flex-wrap justify-end gap-2 px-4 py-3">
          {step === "email" && !recorded ? (
            <button
              type="button"
              className={buttonClass}
              disabled={busy || previewLoading}
              onClick={() => setStep("details")}
            >
              <ArrowLeft size={14} aria-hidden /> Edit details
            </button>
          ) : null}
          <button type="button" className={buttonClass} onClick={onCancel} disabled={busy || previewLoading}>
            {recorded ? "Close" : "Cancel"}
          </button>
          {step === "details" ? (
            <button
              type="button"
              className={primaryButtonClass}
              disabled={!valid || busy || previewLoading}
              onClick={() => void loadEmailPreview()}
            >
              {previewLoading ? "Preparing email…" : "Preview email to HR"}
            </button>
          ) : recorded ? null : (
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy || !emailDraft}
              onClick={() => void confirmSubmit()}
            >
              <Send size={16} aria-hidden />
              {busy ? "Sending…" : "Send to HR (mock) & create rows"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}