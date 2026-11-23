import { useMemo, useState } from "react";

import type { AuditEvent, HiringRequest } from "../../api/staffing";
import {
  Card,
  EmptyBlock,
  Pill,
  buttonClass,
  fieldClass,
  labelClass,
  primaryButtonClass,
} from "../../components/ui/primitives";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassDense, tableHeadClass } from "../../components/ui/tableClasses";

import { formatWhen } from "../../lib/candidateStatus";
import { MnhEmailPreview } from "../pools/MnhEmailPreview";
import type { MnhEmailDraft } from "../../lib/mnhEmailTemplate";

function emailDraftFromPayload(payload: Record<string, unknown> | undefined): MnhEmailDraft | null {
  if (!payload) return null;
  const top = payload.email_draft as MnhEmailDraft | undefined;
  if (top?.body_text) return top;
  const wrapped = payload.payload as Record<string, unknown> | undefined;
  const nested = wrapped?.email_draft as MnhEmailDraft | undefined;
  return nested?.body_text ? nested : null;
}

function hiringContext(payload: Record<string, unknown> | undefined): string {
  if (!payload) return "—";
  const inner = (payload.payload as Record<string, unknown> | undefined) ?? payload;
  const parts: string[] = [];
  if (inner.position_id) parts.push(`Role ${String(inner.position_id)}`);
  if (inner.start_date && inner.end_date) {
    parts.push(`${String(inner.start_date).slice(0, 10)} → ${String(inner.end_date).slice(0, 10)}`);
  }
  if (inner.source === "resource_vision_empty_pool") parts.push("From empty pool");
  return parts.length ? parts.join(" · ") : "—";
}

function summarize(details: Record<string, unknown>): string {
  const parts = Object.entries(details)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  return parts.join(" · ") || "–";
}

export function AuditTab({
  hiring,
  events,
  capabilities,
  busy,
  onRequestHiring,
}: {
  hiring: HiringRequest[];
  events: AuditEvent[];
  capabilities: string[];
  busy: boolean;
  onRequestHiring: (capability: string, headcount: number, justification: string) => void;
}) {
  const [capability, setCapability] = useState("");
  const [headcount, setHeadcount] = useState(1);
  const [why, setWhy] = useState("Internal staffing shortage");
  const [emailViewId, setEmailViewId] = useState<string | null>(null);
  const emailView = useMemo(
    () => hiring.find((h) => h.id === emailViewId),
    [emailViewId, hiring],
  );
  const emailDraft = emailView ? emailDraftFromPayload(emailView.payload) : null;

  return (
    <div className="space-y-4">
      <Card
        title="Request hiring through MyNextHire"
        subtitle="Use when the pool has no suitable employee. The request is stored and sent to MyNextHire."
      >
        <form
          className="grid gap-3 sm:grid-cols-[minmax(10rem,1fr)_7rem_minmax(12rem,2fr)_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            if (capability.trim()) onRequestHiring(capability.trim(), Math.max(1, headcount), why.trim() || "Internal staffing shortage");
          }}
        >
          <label>
            <span className={labelClass}>Capability</span>
            <input
              className={fieldClass}
              list="capability-options"
              value={capability}
              onChange={(e) => setCapability(e.target.value)}
              placeholder="e.g. Data Engineering"
            />
            <datalist id="capability-options">
              {capabilities.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </label>
          <label>
            <span className={labelClass}>Headcount</span>
            <input
              type="number"
              min={1}
              className={fieldClass}
              value={headcount}
              onChange={(e) => setHeadcount(Number(e.target.value) || 1)}
            />
          </label>
          <label>
            <span className={labelClass}>Justification</span>
            <input className={fieldClass} value={why} onChange={(e) => setWhy(e.target.value)} />
          </label>
          <button type="submit" className={primaryButtonClass} disabled={busy || !capability.trim()}>
            Submit request
          </button>
        </form>
      </Card>

      <TableCard title="MNH requests" count={`${hiring.length}`}>
        {hiring.length === 0 ? (
          <div className="p-4">
            <EmptyBlock message="No hiring requests for this project." />
          </div>
        ) : (
          <TableScroll label="MyNextHire requests">
            <table className={`${tableClassDense} min-w-[40rem]`}>
              <thead>
                <tr>
                  <th className={tableHeadClass}>Capability</th>
                  <th className={`${tableHeadClass} text-right`}>Headcount</th>
                  <th className={tableHeadClass}>Project context</th>
                  <th className={tableHeadClass}>Justification</th>
                  <th className={tableHeadClass}>Status</th>
                  <th className={tableHeadClass}>Raised</th>
                  <th className={tableHeadClass}>
                    <span className="sr-only">Email</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {hiring.map((h) => (
                  <tr key={h.id}>
                    <td className="font-medium text-ink">{h.capability}</td>
                    <td className="text-right tabular-nums">{h.headcount}</td>
                    <td className="max-w-[14rem] text-xs text-ink-soft">{hiringContext(h.payload)}</td>
                    <td>{h.justification}</td>
                    <td>
                      <Pill fg="var(--color-warning)">{h.status}</Pill>
                    </td>
                    <td className="text-xs text-muted">{formatWhen(h.created_at)}</td>
                    <td>
                      {emailDraftFromPayload(h.payload) ? (
                        <button type="button" className="text-xs font-medium text-primary" onClick={() => setEmailViewId(h.id)}>
                          View email
                        </button>
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </TableCard>

      {emailViewId && emailDraft ? (
        <div
          className="rv-backdrop fixed inset-0 z-[60] flex items-center justify-center bg-[color-mix(in_srgb,var(--color-ink)_42%,transparent)] p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setEmailViewId(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mnh-audit-email-title"
            className="rv-dialog rv-frame flex max-h-[min(88dvh,40rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-elevated)]"
          >
            <header className="rv-rule-b flex items-start justify-between gap-2 px-4 py-3">
              <div>
                <h2 id="mnh-audit-email-title" className="text-base font-semibold text-ink">
                  MNH email · {emailView?.capability}
                </h2>
                <p className="text-xs text-muted">Stored draft (not sent yet)</p>
              </div>
              <button type="button" className={buttonClass} onClick={() => setEmailViewId(null)}>
                Close
              </button>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto bg-canvas p-4">
              <MnhEmailPreview draft={emailDraft} recorded />
            </div>
          </div>
        </div>
      ) : null}

      <TableCard title="Events" count={`${events.length}`} description="Most recent staffing actions across all projects.">
        {events.length === 0 ? (
          <div className="p-4">
            <EmptyBlock message="No events recorded yet." />
          </div>
        ) : (
          <TableScroll label="Audit events" className="max-h-[28rem]">
            <table className={`${tableClassDense} min-w-[44rem]`}>
              <thead>
                <tr>
                  <th className={tableHeadClass}>When</th>
                  <th className={tableHeadClass}>Actor</th>
                  <th className={tableHeadClass}>Action</th>
                  <th className={tableHeadClass}>Details</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap text-xs text-muted">{formatWhen(e.created_at)}</td>
                    <td>{e.actor}</td>
                    <td className="font-medium text-ink">{e.action.replace(/_/g, " ")}</td>
                    <td className="max-w-[28rem] truncate text-xs text-muted" title={summarize(e.details)}>
                      {summarize(e.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </TableCard>
    </div>
  );
}
