import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { staffingJson } from "../../api/client";
import { staffingApi } from "../../api/staffing";
import { SelectField, buttonClass, fieldClass, labelClass, primaryButtonClass } from "../../components/ui/primitives";
import {
  DEV_LAUNCH_TOKEN,
  stripLaunchFilters,
  type LaunchPayload,
  type PoolsSelectionResult,
} from "../../lib/launch";

import { AllocationHoursStep, type AllocationCommitPlan } from "./AllocationHoursStep";
import { buildHiringRequestFromPool } from "../../lib/hiringRequest";
import type { HiringRequestSubmit } from "../../lib/hiringRequest";

import { MyNextHireRequestDialog } from "./MyNextHireRequestDialog";
import { PoolEmployeeTable } from "./PoolEmployeeTable";
import { PoolsInheritedBanner } from "./PoolsInheritedBanner";
import { SkillRequirementsEditor, type SkillRow } from "./SkillRequirementsEditor";
import type { PoolEmployee, PoolSearchMeta } from "./types";

export type PoolsWizardStep = "pool" | "hours";

export function ResourceVisionPoolsPanel({
  launch,
  onCancel,
  onComplete,
  onMnhRecorded,
  onStepChange,
}: {
  launch: LaunchPayload;
  onCancel: () => void;
  onComplete: (result: PoolsSelectionResult) => void;
  onMnhRecorded?: (slotCount: number, roleId?: string) => void;
  onStepChange?: (step: PoolsWizardStep) => void;
}) {
  const [skills, setSkills] = useState<SkillRow[]>(() => launch.required_skills ?? []);
  const [skillLevels, setSkillLevels] = useState<string[]>(["Foundational", "Applied", "Advanced", "Expert"]);
  const [skillNames, setSkillNames] = useState<string[]>([]);
  const [skillsCatalogLoading, setSkillsCatalogLoading] = useState(true);
  const [pool, setPool] = useState<PoolEmployee[]>([]);
  const [meta, setMeta] = useState<PoolSearchMeta | null>(null);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [availabilityFilter, setAvailabilityFilter] = useState("all");
  const [skillMatchFilter, setSkillMatchFilter] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [statusLine, setStatusLine] = useState("");
  const [working, setWorking] = useState(false);
  const [wizardStep, setWizardStep] = useState<PoolsWizardStep>("pool");
  const [pendingAction, setPendingAction] = useState<"direct" | "kb" | "interview" | null>(null);
  const [hoursApiError, setHoursApiError] = useState<string | null>(null);
  const [mnhDraft, setMnhDraft] = useState<HiringRequestSubmit | null>(null);
  const requestSeq = useRef(0);
  const capacityHours = meta?.capacity_hours ?? 176;

  const goStep = (step: PoolsWizardStep) => {
    setWizardStep(step);
    onStepChange?.(step);
  };

  useEffect(() => {
    onStepChange?.("pool");
  }, [onStepChange]);

  useEffect(() => {
    staffingJson<{
      skill_level_order?: string[];
      skills?: { names: string[]; available?: boolean };
    }>("/skills/vocabulary")
      .then((m) => {
        if (m.skill_level_order?.length) setSkillLevels(m.skill_level_order);
        setSkillNames(m.skills?.names ?? []);
      })
      .catch(() => {
        /* defaults */
      })
      .finally(() => setSkillsCatalogLoading(false));
  }, []);

  const runPoolSearch = useCallback(async () => {
    const seq = ++requestSeq.current;
    setPoolError(null);
    setLoading(true);
    setStatusLine("");
    try {
      const data = await staffingJson<{
        employees: PoolEmployee[];
        meta: PoolSearchMeta;
      }>("/pools/search", {
        method: "POST",
        body: JSON.stringify({
          project_id: launch.project_id,
          start_date: launch.start_date,
          end_date: launch.end_date,
          filters: stripLaunchFilters(launch.filters) ?? {},
          required_skills: skills.filter((s) => s.name.trim()),
          month_hours: launch.month_hours ?? [],
          search,
          availability_filter: availabilityFilter,
          skill_match_filter: skillMatchFilter,
          launch_token: launch.launch_token ?? DEV_LAUNCH_TOKEN,
        }),
      });
      if (seq !== requestSeq.current) return;
      setPool(data.employees ?? []);
      setMeta(data.meta ?? null);
      setSelected((prev) => new Set([...prev].filter((k) => (data.employees ?? []).some((e) => e.employee_key === k))));
      setStatusLine(`${data.employees?.length ?? 0} employees shown`);
    } catch (e) {
      if (seq !== requestSeq.current) return;
      setPoolError(e instanceof Error ? e.message : "Search failed");
      setPool([]);
      setStatusLine("");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [launch, skills, search, availabilityFilter, skillMatchFilter]);

  // The first search runs immediately; later ones wait for typing / editing to settle.
  const searchedOnce = useRef(false);
  useEffect(() => {
    const delay = searchedOnce.current ? 300 : 0;
    searchedOnce.current = true;
    const t = window.setTimeout(() => {
      void runPoolSearch();
    }, delay);
    return () => window.clearTimeout(t);
  }, [runPoolSearch]);

  const monthLabels = useMemo(() => {
    if (pool[0]?.months?.length) return pool[0].months.map((m) => m.label);
    return [];
  }, [pool]);

  const stats = useMemo(() => {
    const full = pool.filter((e) => e.skill_ticks.length > 0 && e.skill_ticks.every((t) => t.matched)).length;
    const bench = pool.filter((e) => e.bench_class === "True Bench").length;
    return { full, bench, shown: pool.length, total: meta?.count ?? pool.length };
  }, [pool, meta]);

  const openHoursStep = (action: "direct" | "kb" | "interview") => {
    const keys = [...selected];
    if (!keys.length) {
      setStatusLine("Select at least one employee.");
      return;
    }
    if (!(launch.month_hours ?? []).length) {
      setStatusLine("Set project start and end dates on Project Track so monthly columns are available.");
      return;
    }
    setPendingAction(action);
    setHoursApiError(null);
    setStatusLine("");
    goStep("hours");
  };

  const commitAllocations = async (plans: AllocationCommitPlan[]) => {
    const action = pendingAction;
    if (!action) return;
    setWorking(true);
    setStatusLine(`Starting ${action} for ${plans.length} employee(s)…`);
    const results: Extract<PoolsSelectionResult, { status: "completed" }>["results"] = [];
    const reservations: string[] = [];
    let demandId: string;
    let confirmedCount = 0;
    try {
      const demand = await staffingApi.createDemand({
        project_id: launch.project_id,
        position_id: launch.role_id,
        start_date: launch.start_date,
        end_date: launch.end_date,
        filters: launch.filters ?? {},
        required_skills: skills.filter((s) => s.name.trim()),
        project_status: "confirmed",
      });
      demandId = demand.demand_id;
      const kbPending: { employee_key: string; candidate_id: string }[] = [];
      for (const plan of plans) {
        let candidateId: string | null = null;
        try {
          const cand = await staffingApi.createCandidate(demand.demand_id, plan.employee_key);
          candidateId = cand.candidate_id;
          await staffingApi.setHours(cand.candidate_id, plan.months);
          if (action === "kb") {
            kbPending.push({ employee_key: plan.employee_key, candidate_id: cand.candidate_id });
            continue;
          }
          const step = await staffingApi.action(cand.candidate_id, action);
          if (action === "direct") {
            const fin = await staffingApi.finalCheck(cand.candidate_id);
            reservations.push(...(fin.reservations ?? []));
            if (fin.status === "Confirmed") confirmedCount++;
            results.push({ employee_key: plan.employee_key, ok: true, status: fin.status });
          } else {
            results.push({ employee_key: plan.employee_key, ok: true, status: step.status, message: step.warning });
          }
        } catch (e) {
          if (candidateId) await staffingApi.release(candidateId).catch(() => undefined);
          if (action === "kb" && candidateId) {
            const i = kbPending.findIndex((p) => p.candidate_id === candidateId);
            if (i >= 0) kbPending.splice(i, 1);
          }
          results.push({
            employee_key: plan.employee_key,
            ok: false,
            message: e instanceof Error ? e.message : "failed",
          });
        }
      }
      if (action === "kb" && kbPending.length) {
        try {
          const batch = await staffingApi.kbBatch(
            demand.demand_id,
            kbPending.map((p) => p.candidate_id),
          );
          for (const row of kbPending) {
            results.push({
              employee_key: row.employee_key,
              ok: true,
              status: batch.status,
              message: batch.warning,
            });
          }
        } catch (batchErr) {
          for (const row of kbPending) {
            await staffingApi.release(row.candidate_id).catch(() => undefined);
            results.push({
              employee_key: row.employee_key,
              ok: false,
              message: batchErr instanceof Error ? batchErr.message : "KB batch failed",
            });
          }
        }
      }
    } catch (e) {
      setStatusLine(e instanceof Error ? e.message : "Could not start the staffing request");
      setWorking(false);
      return;
    }
    setWorking(false);
    const done = results.filter((r) => r.ok).map((r) => r.employee_key);
    if (!done.length) {
      setHoursApiError(`Nothing was started. ${results[0]?.message ?? "Check hours and availability."}`.trim());
      return;
    }
    const availability_notice =
      action === "direct"
        ? confirmedCount > 0
          ? `${confirmedCount} allocation(s) confirmed; hours reserved.`
          : undefined
        : `${done.length} employee(s) added. Hours are reserved only after final confirmation.`;
    onComplete({
      status: "completed",
      demand_id: demandId,
      employee_keys: done,
      action,
      reservations,
      role_id: launch.role_id,
      skills: skills.filter((s) => s.name.trim()),
      results,
      availability_notice,
    });
    setSelected(new Set());
    setPendingAction(null);
    goStep("pool");
  };

  const openMnhDialog = useCallback(() => {
    setMnhDraft(
      buildHiringRequestFromPool({
        launch,
        requiredSkills: skills,
        employeesShown: pool.length,
        employeesTotal: meta?.count,
      }),
    );
  }, [launch, skills, pool.length, meta?.count]);

  const submitMnhRequest = async (body: HiringRequestSubmit) => {
    setWorking(true);
    try {
      const res = await staffingApi.requestHiring(body);
      const slots = res.mnh_slots?.length ?? body.headcount;
      setStatusLine(
        `MyNextHire request recorded (${body.headcount} × ${body.capability}). ${slots} row(s) added with status Hiring from MNH.`,
      );
      onMnhRecorded?.(slots, body.position_id);
      const raw = res.email_draft as import("../../lib/mnhEmailTemplate").MnhEmailDraft | undefined;
      if (!raw && !res.mnh_slots?.length) {
        throw new Error("The server did not confirm the request or staffing rows.");
      }
      return raw ?? null;
    } catch (e) {
      setStatusLine(e instanceof Error ? e.message : "Hiring request failed");
      throw e;
    } finally {
      setWorking(false);
    }
  };

  const toggle = (key: string, on: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  if (wizardStep === "hours" && pendingAction) {
    return (
      <AllocationHoursStep
        key={`${pendingAction}-${[...selected].join(",")}`}
        action={pendingAction}
        employeeKeys={[...selected]}
        pool={pool}
        monthHours={launch.month_hours ?? []}
        capacityHours={capacityHours}
        working={working}
        serverError={hoursApiError}
        onBack={() => {
          setPendingAction(null);
          setHoursApiError(null);
          goStep("pool");
        }}
        onConfirm={(plans) => void commitAllocations(plans)}
      />
    );
  }

  const message = poolError ?? (loading ? null : statusLine && !statusLine.endsWith("employees shown") ? statusLine : null);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="rv-pools-layout">
        <aside className="rv-pools-deck" aria-label="Refine the pool">
          <div className="rv-pools-deck__row" aria-labelledby="rv-pools-refine-heading">
            <h3 id="rv-pools-refine-heading" className="rv-pools-deck__rail">
              Refine
            </h3>
            <PoolFiltersBar
              compact
              search={search}
              onSearch={setSearch}
              availabilityFilter={availabilityFilter}
              onAvailability={setAvailabilityFilter}
              skillMatchFilter={skillMatchFilter}
              onSkillMatch={setSkillMatchFilter}
            />
          </div>
          <SkillRequirementsEditor
            compact
            skills={skills}
            levels={skillLevels}
            names={skillNames}
            catalogLoading={skillsCatalogLoading}
            onChange={setSkills}
          />
          <PoolsInheritedBanner compact filters={launch.filters} />
        </aside>

        <div className="rv-pools-results">
          {message ? (
            <p
              role="status"
              className={`rv-pools-message ${poolError ? "rv-pools-message--error" : ""}`}
            >
              {message}
            </p>
          ) : null}
          <PoolEmployeeTable
            rows={pool}
            monthLabels={monthLabels}
            selected={selected}
            loading={loading}
            stats={{ bench: stats.bench, full: stats.full }}
            onToggle={toggle}
            onToggleAll={(keys) => setSelected(new Set(keys))}
            onSelectTop={() => {
              setSelected(new Set(pool.filter((r) => !r.in_flight_status).slice(0, 5).map((r) => r.employee_key)));
            }}
            onClearSelection={() => setSelected(new Set())}
            onRequestHiring={!loading && pool.length === 0 ? openMnhDialog : undefined}
          />
        </div>
      </div>

      <footer className="rv-pools-footer flex shrink-0 flex-wrap items-center gap-2 px-5 py-3.5">
        <span className="mr-auto text-xs font-medium tabular-nums text-ink-soft">
          {working ? "Processing…" : selected.size ? `${selected.size} selected` : "No employees selected"}
        </span>
        {!loading && pool.length === 0 ? (
          <button type="button" className={primaryButtonClass} onClick={openMnhDialog} disabled={working}>
            Send to MyNextHire
          </button>
        ) : null}
        <button type="button" className={buttonClass} onClick={onCancel} disabled={working}>
          Cancel
        </button>
        <span className="hidden h-7 w-px shrink-0 bg-hairline sm:inline-block" aria-hidden />
        <button type="button" className={buttonClass} onClick={() => openHoursStep("kb")} disabled={!selected.size || working}>
          Send to KB
        </button>
        <button type="button" className={buttonClass} onClick={() => openHoursStep("interview")} disabled={!selected.size || working}>
          Book interview
        </button>
        <button type="button" className={primaryButtonClass} onClick={() => openHoursStep("direct")} disabled={!selected.size || working}>
          Direct select
        </button>
      </footer>

      {mnhDraft ? (
        <MyNextHireRequestDialog
          draft={mnhDraft}
          busy={working}
          onCancel={() => setMnhDraft(null)}
          onSubmit={(body) => submitMnhRequest(body)}
        />
      ) : null}
    </div>
  );
}

function PoolFiltersBar({
  compact = false,
  search,
  onSearch,
  availabilityFilter,
  onAvailability,
  skillMatchFilter,
  onSkillMatch,
}: {
  compact?: boolean;
  search: string;
  onSearch: (v: string) => void;
  availabilityFilter: string;
  onAvailability: (v: string) => void;
  skillMatchFilter: string;
  onSkillMatch: (v: string) => void;
}) {
  const label = compact ? "sr-only" : labelClass;
  const field = compact ? `${fieldClass} rv-deck-field` : fieldClass;
  return (
    <div className={`rv-pool-filters ${compact ? "rv-pool-filters--compact" : ""}`}>
      <label className="block min-w-0">
        <span className={label}>Search</span>
        <input
          className={field}
          placeholder="Name or employee ID"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
        />
      </label>
      <label className="block min-w-0">
        <span className={label}>Availability</span>
        <SelectField
          className={compact ? "rv-deck-select" : ""}
          value={availabilityFilter}
          onChange={(e) => onAvailability(e.target.value)}
        >
          <option value="all">All months</option>
          <option value="any">Free in one month</option>
          <option value="every">Free every month</option>
        </SelectField>
      </label>
      <label className="block min-w-0">
        <span className={label}>Skill match</span>
        <SelectField
          className={compact ? "rv-deck-select" : ""}
          value={skillMatchFilter}
          onChange={(e) => onSkillMatch(e.target.value)}
        >
          <option value="all">Any match</option>
          <option value="full">Full match</option>
          <option value="some">Partial match</option>
        </SelectField>
      </label>
    </div>
  );
}
