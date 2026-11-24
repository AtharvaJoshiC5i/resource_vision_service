import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import type { Candidate } from "../../api/staffing";
import { staffingJson } from "../../api/client";
import { staffingApi } from "../../api/staffing";
import type { LaunchPayload } from "../../lib/launch";

import { AllocationHoursStep, type AllocationCommitPlan } from "../pools/AllocationHoursStep";
import type { PoolEmployee } from "../pools/types";
import { monthColumnsFromLaunch } from "../pools/allocationHoursUtils";

type AvailabilityMonth = {
  month: number;
  status: string;
  remaining: number | null;
  planned: number | null;
  bookable_hours?: number;
};

function poolRowFromAvailability(
  candidate: Candidate,
  availability: { employee: { key: string; code: string; name: string }; months: AvailabilityMonth[] },
  launchMonths: { month_key: string; hours: number }[],
): PoolEmployee {
  const projectCols = monthColumnsFromLaunch(launchMonths);
  const byMonth = new Map(availability.months.map((m) => [m.month, m]));
  return {
    employee_key: candidate.employee_key,
    employee_code: availability.employee.code,
    employee_name: availability.employee.name,
    bench_class: "—",
    skill_ticks: [],
    months: projectCols.map((col) => {
      const monthInt = Number(col.iso.slice(0, 4)) * 100 + Number(col.iso.slice(5, 7));
      const em = byMonth.get(monthInt);
      const remaining = em?.remaining ?? 0;
      return {
        month_key: monthInt,
        label: col.label,
        status: em?.status ?? "No record",
        remaining,
        bookable_hours: Math.max(0, remaining ?? 0),
      };
    }),
    interview_leads_count: 0,
  };
}

export function CandidateDirectSelectModal({
  candidate,
  launch,
  onClose,
  onSuccess,
}: {
  candidate: Candidate;
  launch: LaunchPayload;
  onClose: () => void;
  onSuccess: (notice?: string) => void;
}) {
  const [poolRow, setPoolRow] = useState<PoolEmployee | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [hoursApiError, setHoursApiError] = useState<string | null>(null);
  const [capacity, setCapacity] = useState(176);

  const launchMonths = useMemo(() => launch.month_hours ?? [], [launch.month_hours]);
  const savedMonths = useMemo(() => candidate.months ?? [], [candidate.months]);

  useEffect(() => {
    let stale = false;
  const load = async () => {
    try {
      const data = await staffingJson<{
        employees: PoolEmployee[];
        meta?: { capacity_hours?: number };
      }>("/pools/search", {
        method: "POST",
        body: JSON.stringify({
          project_id: launch.project_id,
          start_date: launch.start_date,
          end_date: launch.end_date,
          filters: launch.filters ?? {},
          required_skills: launch.required_skills ?? [],
          month_hours: launchMonths,
          launch_token: launch.launch_token,
        }),
      });
      if (stale) return;
      if (data.meta?.capacity_hours) setCapacity(data.meta.capacity_hours);
      const row =
        data.employees.find((e) => e.employee_key.toUpperCase() === candidate.employee_key.toUpperCase()) ?? null;
      if (row) {
        setPoolRow(row);
        setLoadError(null);
        return;
      }
      const avail = await staffingJson<{
        employee: { key: string; code: string; name: string };
        months: AvailabilityMonth[];
      }>(`/availability/employee/${encodeURIComponent(candidate.employee_key)}`);
      if (stale) return;
      setPoolRow(poolRowFromAvailability(candidate, avail, launchMonths));
      setLoadError(null);
    } catch (e: unknown) {
      if (!stale) setLoadError(e instanceof Error ? e.message : "Could not load availability");
    }
  };
    void load();
    return () => {
      stale = true;
    };
  }, [candidate.employee_key, candidate.employee_code, candidate.employee_name, launch, launchMonths]);

  const commit = async (plans: AllocationCommitPlan[]) => {
    const plan = plans[0];
    if (!plan) return;
    setWorking(true);
    setHoursApiError(null);
    try {
      await staffingApi.setHours(candidate.id, plan.months);
      await staffingApi.action(candidate.id, "direct");
      const fin = await staffingApi.finalCheck(candidate.id);
      const notice =
        fin.status === "Confirmed"
          ? "Hours reserved and availability updated; Project Track write recorded (stub until Azure write access is enabled)."
          : fin.status === "Reserved"
            ? "Hours reserved. Project Track write is pending — use Retry PT write on the role row."
            : undefined;
      onSuccess(notice);
    } catch (e) {
      setHoursApiError(e instanceof Error ? e.message : "Direct select failed");
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="rv-backdrop fixed inset-0 z-[60] flex items-end justify-center bg-[color-mix(in_srgb,var(--color-ink)_48%,transparent)] p-0 sm:items-center sm:p-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="direct-select-title"
        className="rv-dialog rv-density flex h-[min(88dvh,720px)] w-full max-w-4xl flex-col overflow-hidden rounded-t-2xl border border-hairline bg-surface shadow-[var(--shadow-elevated)] sm:rounded-2xl"
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hairline px-4 py-3">
          <div>
            <p className="rv-eyebrow text-[0.625rem]">Direct select</p>
            <h2 id="direct-select-title" className="text-base font-semibold text-ink">
              {candidate.employee_name}
            </h2>
          </div>
          <button type="button" className="rv-btn-secondary" aria-label="Close" onClick={onClose} disabled={working}>
            <X size={18} aria-hidden />
          </button>
        </header>
        {loadError ? (
          <p className="px-4 py-6 text-sm text-error-ink">{loadError}</p>
        ) : poolRow ? (
          <AllocationHoursStep
            key={`${candidate.id}-${savedMonths.map((m) => m.hours).join(",")}`}
            action="direct"
            employeeKeys={[candidate.employee_key]}
            pool={[poolRow]}
            monthHours={launchMonths}
            capacityHours={capacity}
            working={working}
            serverError={hoursApiError}
            savedMonths={savedMonths}
            onBack={onClose}
            onConfirm={(plans) => void commit(plans)}
          />
        ) : (
          <p className="px-4 py-6 text-sm text-muted">Loading bookable hours…</p>
        )}
      </div>
    </div>
  );
}