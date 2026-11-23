import { useCallback, useEffect, useMemo, useState } from "react";

import { staffingApi, type Candidate } from "../../api/staffing";
import { staffingJson } from "../../api/client";
import { filterOptionsFromStaffingMeta, type ProjectTrackFilterOptions } from "../../api/staffingMeta";

import { BookOpenCheck, CalendarClock, CircleCheckBig, Sparkles, Users } from "lucide-react";

import { AppHeader } from "../../components/layout/AppHeader";
import { StatStrip } from "../../components/ui/StatStrip";
import { Toast, type ToastMessage } from "../../components/ui/Toast";
import { toneFor } from "../../lib/toast";
import {
  Card,
  EmptyBlock,
  ErrorBlock,
  buttonClass,
  fieldClass,
  labelClass,
} from "../../components/ui/primitives";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassDense, tableHeadClass } from "../../components/ui/tableClasses";
import { useActionRunner, useProjectWorkflow } from "../../hooks/useProjectWorkflow";
import { roleToLaunch, type LaunchPayload, type PoolsSelectionResult, type ResourceRole } from "../../lib/launch";
import { ResourceVisionPoolsModal } from "../pools/ResourceVisionPoolsModal";

import { AuditTab } from "./AuditTab";
import { FINISHED, formatWhen } from "../../lib/candidateStatus";
import { KnowledgeBenchmarkingTab } from "./KnowledgeBenchmarkingTab";
import { CandidateDirectSelectModal } from "./CandidateDirectSelectModal";
import { InterviewResultsDialog, type InterviewResultsChoice } from "./InterviewResultsDialog";
import { PostTrainingPathDialog } from "./PostTrainingPathDialog";
import { ProjectHero } from "./ProjectHero";
import { RoleTable } from "./RoleTable";

type TabId = "project" | "kb" | "audit";

const MAX_WINDOW_MONTHS = 12;

function windowMonths(startIso: string, endIso: string): string[] {
  const out: string[] = [];
  const start = new Date(`${startIso.slice(0, 7)}-01T00:00:00Z`);
  const end = new Date(`${endIso.slice(0, 7)}-01T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return out;
  for (let d = new Date(start); d <= end && out.length < MAX_WINDOW_MONTHS; d.setUTCMonth(d.getUTCMonth() + 1)) {
    out.push(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`);
  }
  return out;
}

function newRole(index: number): ResourceRole {
  return {
    id: `role-${index}`,
    primary: "",
    secondary: "",
    department: "",
    location: "",
    country: "",
    grade: "",
    skills: [],
    monthHours: [],
    status: "Open",
  };
}

const EMPTY_OPTIONS: ProjectTrackFilterOptions = {
  primary_capability: [],
  secondary_capability: [],
  department: [],
  location: [],
  country: [],
  grade: [],
};

export function ProjectTrackPage() {
  const [tab, setTab] = useState<TabId>("project");
  const [projectId, setProjectId] = useState("P-SIM-001");
  const [proposal] = useState("PROP-2027-ENG-014");
  const [startDate, setStartDate] = useState("2026-12-01");
  const [endDate, setEndDate] = useState("2027-06-30");
  const [options, setOptions] = useState<ProjectTrackFilterOptions>(EMPTY_OPTIONS);
  const [roles, setRoles] = useState<ResourceRole[]>(() => [newRole(1)]);
  const [dataMode, setDataMode] = useState<"azure" | "demo" | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const setActivity = useCallback((text: string) => setToast({ id: Date.now(), text, tone: toneFor(text) }), []);
  const dismissToast = useCallback(() => setToast(null), []);
  const [poolLaunch, setPoolLaunch] = useState<LaunchPayload | null>(null);
  const [interviewResults, setInterviewResults] = useState<Candidate | null>(null);
  const [postTrainingPath, setPostTrainingPath] = useState<Candidate | null>(null);
  const [directSelectCtx, setDirectSelectCtx] = useState<{ candidate: Candidate; launch: LaunchPayload } | null>(
    null,
  );

  const workflow = useProjectWorkflow(projectId);
  const { busy, run } = useActionRunner(workflow.reloadAll, setActivity);

  const months = useMemo(() => windowMonths(startDate, endDate), [startDate, endDate]);
  /** Month columns for the pool hours step only — effort is entered per employee in the popup. */
  const monthHours = useMemo(() => months.map((m) => ({ month_key: m, hours: 0 })), [months]);
  const windowInvalid = endDate < startDate;

  useEffect(() => {
    staffingJson<{ options?: Record<string, string[]>; runtime?: { data_mode?: string } }>("/filters")
      .then((data) => {
        setOptions(filterOptionsFromStaffingMeta(data));
        setDataMode(data.runtime?.data_mode === "demo" ? "demo" : data.runtime?.data_mode === "azure" ? "azure" : null);
        setMetaError(null);
      })
      .catch((err) => setMetaError(err instanceof Error ? err.message : "Request failed"));
  }, []);

  const updateRole = (id: string, patch: Partial<ResourceRole>) =>
    setRoles((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const launchForCandidate = useCallback(
    (c: Candidate): LaunchPayload | null => {
      const role = roles.find((r) => r.id === c.position_id);
      if (!role) return null;
      return roleToLaunch(projectId, startDate, endDate, { ...role, monthHours }, window.location.origin);
    },
    [roles, projectId, startDate, endDate, monthHours],
  );

  const openPostTrainingPath = useCallback(
    async (candidateId: string, fallback?: Candidate) => {
      try {
        const fresh =
          (await staffingApi.workflow(projectId)).candidates.find((c) => c.id === candidateId) ??
          (fallback?.id === candidateId ? fallback : undefined);
        if (fresh?.status === "Skills Matched") {
          setPostTrainingPath(fresh);
          setTab("project");
        } else if (fallback?.status === "Skills Matched") {
          setPostTrainingPath(fallback);
          setTab("project");
        }
      } catch {
        if (fallback?.status === "Skills Matched") {
          setPostTrainingPath(fallback);
          setTab("project");
        }
      }
    },
    [projectId],
  );

  const completeSelectionAfterInterview = useCallback(
    async (c: Candidate) => {
      const workflowBody = await staffingApi.workflow(projectId);
      const fresh = workflowBody.candidates.find((x) => x.id === c.id) ?? c;
      const hasHours = fresh.months?.some((m) => m.hours > 0);
      if (hasHours) {
        try {
          const fin = await staffingApi.finalCheck(fresh.id);
          if (fin.status === "Confirmed") {
            setActivity(`${fresh.employee_name} is confirmed on this project after the interview.`);
            return;
          }
          if (fin.status === "Reserved") {
            setActivity(
              `${fresh.employee_name} is reserved after the interview. Use Retry PT write on the role row if allocation is still pending.`,
            );
            return;
          }
        } catch {
          /* capacity or PT issues — fall through to direct select */
        }
      }
      const launch = launchForCandidate(fresh);
      if (!launch) {
        throw new Error("Could not resolve the role for this candidate. Check that the resource role still exists.");
      }
      setDirectSelectCtx({ candidate: fresh, launch });
      setActivity(`${fresh.employee_name} passed the interview. Confirm or adjust monthly hours to finish allocation.`);
    },
    [launchForCandidate, projectId, setActivity],
  );

  const openPoolsForRole = (roleId: string) => {
    const role = roles.find((r) => r.id === roleId);
    if (!role) return;
    if (windowInvalid || monthHours.length === 0) {
      setActivity("Fix the project dates first: the end date must not be before the start date.");
      return;
    }
    setPoolLaunch(roleToLaunch(projectId, startDate, endDate, { ...role, monthHours }, window.location.origin));
  };

  const onPoolsComplete = useCallback(
    (result: PoolsSelectionResult) => {
      setPoolLaunch(null);
      if (result.status !== "completed") return;
      setRoles((prev) =>
        prev.map((r) =>
          r.id === result.role_id && result.skills ? { ...r, skills: result.skills } : r,
        ),
      );
      const failed = result.results.filter((r) => !r.ok);
      const okCount = result.results.length - failed.length;
      const actionLabel =
        result.action === "direct" ? "Direct select" : result.action === "kb" ? "KB" : "Interview";
      setActivity(
        `${okCount} employee(s) processed via ${actionLabel}.` +
          (result.availability_notice ? ` ${result.availability_notice}` : "") +
          (failed.length ? ` ${failed.length} failed: ${failed.map((f) => `${f.employee_key} (${f.message})`).join("; ")}` : ""),
      );
      void workflow.reloadAll();
    },
    [workflow, setActivity],
  );

  const handlers = {
    busy,
    onFinalCheck: (c: Candidate) => run(c.id, "Final check", () => staffingApi.finalCheck(c.id)),
    onRelease: (c: Candidate) => run(c.id, "Release", () => staffingApi.release(c.id)),
    onInterviewResults: (c: Candidate) => setInterviewResults(c),
    onBookInterview: (c: Candidate) =>
      run(c.id, "Book interview", () => staffingApi.action(c.id, "interview")),
    onDirectSelect: (c: Candidate) => {
      const launch = launchForCandidate(c);
      if (!launch) {
        setActivity("Could not resolve the role for this candidate.");
        return;
      }
      setDirectSelectCtx({ candidate: c, launch });
    },
    onRetryKb: (c: Candidate) => run(c.id, "KB request", () => staffingApi.action(c.id, "kb")),
  };

  const fireDateChange = () =>
    run("event", "Date change event", () => staffingApi.fireEvent("dates_changed", projectId, { start_date: startDate, end_date: endDate }));

  const live = workflow.candidates.filter((c) => !FINISHED.has(c.status));
  const count = (...s: string[]) => live.filter((c) => s.includes(c.status)).length;
  const rejected = workflow.interviews.filter((i) => i.status === "Rejected");
  const byCandidate = new Map(workflow.candidates.map((c) => [c.id, c]));
  const kbOpen = workflow.kbRequests.filter((r) => r.status === "Training" || r.status === "Sent").length;

  return (
    <div className="rv-density min-w-0 w-full">
      <AppHeader projectId={projectId} dataMode={dataMode} />
      <main className="rv-container space-y-4 pb-10 pt-5 md:space-y-5">
      <ProjectHero<TabId>
        proposal={proposal}
        projectId={projectId}
        startDate={startDate}
        endDate={endDate}
        months={months.length}
        tab={tab}
        onTab={setTab}
        tabs={[
          { value: "project", label: "Resourcing" },
          { value: "kb", label: "Knowledge Benchmarking", count: kbOpen },
          { value: "audit", label: "Audit & hiring" },
        ]}
        actions={
          <button type="button" className={buttonClass} disabled={busy === "event"} onClick={fireDateChange}>
            <CalendarClock size={14} aria-hidden />
            Simulate date change
          </button>
        }
      />

      <div className="min-w-0 space-y-3 md:space-y-4">
        {metaError ? (
          <ErrorBlock message={`${metaError}. Start the staffing API on port 8010 and open this UI via npm run dev.`} />
        ) : null}
        {workflow.error && !metaError ? <ErrorBlock message={workflow.error} onRetry={() => void workflow.reloadAll()} /> : null}

        {tab === "project" ? (
          <>
            <StatStrip
              label="Staffing workflow"
              stats={[
                { label: "Open roles", value: roles.length, icon: Users, tone: "neutral" },
                { label: "In training", value: count("KB Pending", "Training"), icon: BookOpenCheck, tone: "warning" },
                { label: "Interviews", value: count("Interview Pending", "Interview Booked"), icon: CalendarClock, tone: "primary" },
                { label: "Skills matched", value: count("Skills Matched"), icon: Sparkles, tone: "primary" },
                { label: "Confirmed", value: count("Reserved", "Confirmed"), icon: CircleCheckBig, tone: "success" },
              ]}
            />

            <Card
              title="Engagement details"
              subtitle="Monthly effort is entered per employee when selecting from the pool."
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label>
                  <span className={labelClass}>Project ID</span>
                  <input className={fieldClass} value={projectId} onChange={(e) => setProjectId(e.target.value.trim())} />
                </label>
                <label>
                  <span className={labelClass}>Proposal</span>
                  <input className={fieldClass} value={proposal} readOnly />
                </label>
                <label>
                  <span className={labelClass}>Start date</span>
                  <input type="date" className={fieldClass} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </label>
                <label>
                  <span className={labelClass}>End date</span>
                  <input
                    type="date"
                    className={fieldClass}
                    value={endDate}
                    aria-invalid={windowInvalid}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </label>
              </div>
              {windowInvalid ? (
                <p role="alert" className="mt-2 text-xs text-error-ink">
                  The end date must not be before the start date.
                </p>
              ) : null}
            </Card>

            <RoleTable
              roles={roles}
              options={options}
              candidates={workflow.candidates}
              mnhSlots={workflow.mnhSlots}
              handlers={handlers}
              monthKeys={months}
              onChange={updateRole}
              onAdd={() => setRoles((prev) => [...prev, newRole(Math.max(0, ...prev.map((r) => Number(r.id.split("-")[1]))) + 1)])}
              onRemove={(id) => setRoles((prev) => prev.filter((r) => r.id !== id))}
              onSelect={openPoolsForRole}
            />

            <TableCard title="Previously rejected candidates" count={`${rejected.length}`}>
              {rejected.length === 0 ? (
                <div className="p-4">
                  <EmptyBlock message="No candidates have been rejected for this project." />
                </div>
              ) : (
                <TableScroll label="Rejected candidates">
                  <table className={`${tableClassDense} min-w-[40rem]`}>
                    <thead>
                      <tr>
                        <th className={tableHeadClass}>Employee</th>
                        <th className={tableHeadClass}>Type</th>
                        <th className={tableHeadClass}>Reason</th>
                        <th className={tableHeadClass}>Interviewed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rejected.map((i) => (
                        <tr key={i.id}>
                          <td className="font-medium text-ink">{byCandidate.get(i.candidate_id)?.employee_name ?? i.employee_key}</td>
                          <td>{i.rejection_type ?? "–"}</td>
                          <td>{i.rejection_reason ?? "–"}</td>
                          <td className="text-xs text-muted">{formatWhen(i.booked_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableScroll>
              )}
            </TableCard>
          </>
        ) : null}

        {tab === "kb" ? (
          <KnowledgeBenchmarkingTab
            requests={workflow.kbRequests}
            candidates={workflow.candidates}
            interviews={workflow.interviews}
            busy={busy}
            onOutcome={(c, outcome) =>
              void run(c.id, outcome === "success" ? "Training completion" : "Training failure", () =>
                staffingApi.trainingOutcome(c.id, outcome),
              ).then(() => {
                if (outcome === "success") {
                  void openPostTrainingPath(c.id, { ...c, status: "Skills Matched" });
                }
              })
            }
            onRetry={handlers.onRetryKb}
          />
        ) : null}

        {tab === "audit" ? (
          <AuditTab
            hiring={workflow.hiringRequests}
            events={workflow.audit}
            capabilities={options.primary_capability}
            busy={busy === "hire"}
            onRequestHiring={(cap, n, why) =>
              run("hire", "Hiring request", () =>
                staffingApi.requestHiring({
                  project_id: projectId,
                  capability: cap,
                  headcount: n,
                  justification: why,
                  source: "project_track_audit",
                }),
              )
            }
          />
        ) : null}

      </div>

      </main>

      <Toast toast={toast} onDismiss={dismissToast} />

      {poolLaunch ? (
        <ResourceVisionPoolsModal
          key={poolLaunch.role_id}
          launch={poolLaunch}
          onClose={() => {
            setPoolLaunch(null);
            setActivity("Resource Vision Pools closed without a selection.");
          }}
          onComplete={onPoolsComplete}
          onMnhRecorded={(slotCount, roleId) => {
            setPoolLaunch(null);
            setActivity(
              `${slotCount} MyNextHire position(s) added on role ${roleId ?? "—"} with status Hiring from MNH.`,
            );
            void workflow.reloadAll();
          }}
        />
      ) : null}

      {postTrainingPath ? (
        <PostTrainingPathDialog
          employeeName={postTrainingPath.employee_name}
          busy={busy === postTrainingPath.id}
          onCancel={() => setPostTrainingPath(null)}
          onInterview={() => {
            const c = postTrainingPath;
            setPostTrainingPath(null);
            void run(c.id, "Book interview", () => staffingApi.action(c.id, "interview")).then(() => {
              setTab("project");
              setActivity(
                `${c.employee_name} is booked for interview. When the interview is done, use Interview results on the role row.`,
              );
            });
          }}
          onDirectSelect={() => {
            const c = postTrainingPath;
            setPostTrainingPath(null);
            const launch = launchForCandidate(c);
            if (launch) setDirectSelectCtx({ candidate: c, launch });
            else setActivity("Could not resolve the role for this candidate.");
          }}
        />
      ) : null}

      {directSelectCtx ? (
        <CandidateDirectSelectModal
          candidate={directSelectCtx.candidate}
          launch={directSelectCtx.launch}
          onClose={() => setDirectSelectCtx(null)}
          onSuccess={(notice) => {
            const name = directSelectCtx.candidate.employee_name;
            setDirectSelectCtx(null);
            setActivity(`${name} confirmed via direct select.${notice ? ` ${notice}` : ""}`);
            void workflow.reloadAll();
          }}
        />
      ) : null}

      {interviewResults ? (
        <InterviewResultsDialog
          employeeName={interviewResults.employee_name}
          employeeCode={interviewResults.employee_code}
          busy={busy === interviewResults.id}
          onCancel={() => setInterviewResults(null)}
          onSubmit={(choice: InterviewResultsChoice) => {
            const c = interviewResults;
            setInterviewResults(null);
            if (choice.outcome === "pass") {
              void run(c.id, "Select employee", async () => {
                await staffingApi.interviewOutcome(c.id, "pass");
                await completeSelectionAfterInterview(c);
              });
              return;
            }
            void run(c.id, "Interview rejection", () =>
              staffingApi.interviewOutcome(c.id, "reject", choice.rejectionType, choice.reason),
            ).then(() => {
              setActivity(
                choice.rejectionType === "Technical"
                  ? `${c.employee_name} rejected (technical). Feedback sent to Knowledge Benchmarking and listed under Previously rejected candidates.`
                  : `${c.employee_name} rejected (non-technical). Recorded under Previously rejected candidates.`,
              );
            });
          }}
        />
      ) : null}
    </div>
  );
}
