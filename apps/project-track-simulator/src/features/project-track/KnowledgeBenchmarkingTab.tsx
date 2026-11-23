import type { Candidate, Interview, KbRequest } from "../../api/staffing";
import { KpiBand, KpiGroup, KpiStat } from "../../components/ui/KpiBand";
import { EmptyBlock, Pill, buttonClass, primaryButtonClass } from "../../components/ui/primitives";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassDense, tableHeadClass } from "../../components/ui/tableClasses";

import { formatWhen } from "../../lib/candidateStatus";

const KB_COLOR: Record<KbRequest["status"], string> = {
  Sent: "var(--color-muted)",
  Training: "var(--color-warning)",
  Completed: "var(--color-success)",
  Failed: "var(--color-error)",
  Rejected: "var(--color-error)",
};

export function KnowledgeBenchmarkingTab({
  requests,
  candidates,
  interviews,
  busy,
  onOutcome,
  onRetry,
}: {
  requests: KbRequest[];
  candidates: Candidate[];
  interviews: Interview[];
  busy: string | null;
  onOutcome: (c: Candidate, outcome: "success" | "failed") => void;
  onRetry: (c: Candidate) => void;
}) {
  const byId = new Map(candidates.map((c) => [c.id, c]));
  const name = (r: KbRequest) => byId.get(r.candidate_id)?.employee_name ?? r.employee_key;
  const count = (s: KbRequest["status"]) => requests.filter((r) => r.status === s).length;
  const technical = interviews.filter((i) => i.status === "Rejected" && i.rejection_type === "Technical");

  return (
    <div className="space-y-4">
      <KpiBand label="Knowledge Benchmarking summary">
        <KpiGroup title="Requests" columns={4}>
          <KpiStat label="Sent" value={requests.length} />
          <KpiStat label="In training" value={count("Training")} />
          <KpiStat label="Completed" value={count("Completed")} />
          <KpiStat label="Failed / rejected" value={count("Failed") + count("Rejected")} />
        </KpiGroup>
      </KpiBand>

      <TableCard
        title="Requests sent to Knowledge Benchmarking"
        count={`${requests.length}`}
        description="Training days are 85% of the time before the project starts; the remaining 15% is buffer."
      >
        {requests.length === 0 ? (
          <div className="p-4">
            <EmptyBlock message="No candidates have been sent to Knowledge Benchmarking. Use Send to KB in Resource Vision Pools." />
          </div>
        ) : (
          <TableScroll label="Knowledge Benchmarking requests">
            <table className={`${tableClassDense} min-w-[48rem]`}>
              <thead>
                <tr>
                  <th className={tableHeadClass}>Employee</th>
                  <th className={tableHeadClass}>Status</th>
                  <th className={`${tableHeadClass} text-right`}>Training days</th>
                  <th className={`${tableHeadClass} text-right`}>Buffer days</th>
                  <th className={tableHeadClass}>Updated</th>
                  <th className={tableHeadClass}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => {
                  const cand = byId.get(r.candidate_id);
                  return (
                    <tr key={r.id}>
                      <td className="font-medium text-ink">{name(r)}</td>
                      <td>
                        <Pill fg={KB_COLOR[r.status]}>{r.status}</Pill>
                        {r.reason ? <span className="ml-2 text-xs text-muted">{r.reason}</span> : null}
                      </td>
                      <td className="text-right tabular-nums">{r.training_days}</td>
                      <td className="text-right tabular-nums">{r.buffer_days}</td>
                      <td className="text-xs text-muted">{formatWhen(r.updated_at)}</td>
                      <td>
                        {cand && cand.status === "Training" ? (
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              className={primaryButtonClass}
                              disabled={busy === cand.id}
                              onClick={() => onOutcome(cand, "success")}
                            >
                              Training complete
                            </button>
                            <button
                              type="button"
                              className={buttonClass}
                              disabled={busy === cand.id}
                              onClick={() => onOutcome(cand, "failed")}
                            >
                              Mark failed
                            </button>
                          </div>
                        ) : null}
                        {cand && cand.status === "KB Pending" ? (
                          <button type="button" className={buttonClass} disabled={busy === cand.id} onClick={() => onRetry(cand)}>
                            Retry request
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableScroll>
        )}
      </TableCard>

      <TableCard title="Technical rejection feedback received from interviews" count={`${technical.length}`}>
        {technical.length === 0 ? (
          <div className="p-4">
            <EmptyBlock message="No technical rejections yet." />
          </div>
        ) : (
          <ul className="divide-y divide-hairline">
            {technical.map((i) => (
              <li key={i.id} className="px-4 py-3 text-sm sm:px-5">
                <span className="font-medium text-ink">{byId.get(i.candidate_id)?.employee_name ?? i.employee_key}</span>
                <span className="ml-2 text-xs text-muted">{formatWhen(i.booked_at)}</span>
                <p className="mt-0.5 text-ink-soft">{i.rejection_reason}</p>
              </li>
            ))}
          </ul>
        )}
      </TableCard>
    </div>
  );
}
