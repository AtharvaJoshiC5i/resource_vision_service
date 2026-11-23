import { Fragment } from "react";
import { Plus, Trash2 } from "lucide-react";

import type { Candidate, MnhStaffingSlot } from "../../api/staffing";
import type { ProjectTrackFilterOptions } from "../../api/staffingMeta";
import { primaryButtonClass, quietButtonClass } from "../../components/ui/primitives";
import { RoleFilterSelect } from "./RoleFilterSelect";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassDense, tableHeadClass } from "../../components/ui/tableClasses";
import type { ResourceRole } from "../../lib/launch";

import { FINISHED, roleStatusForRole } from "../../lib/candidateStatus";

import { CandidateStatusPill } from "./CandidateStatus";
import { RoleCandidatesTable } from "./RoleCandidatesTable";
import { RoleMnhSlotsTable } from "./RoleMnhSlotsTable";

const FILTER_COLUMNS: { key: keyof ProjectTrackFilterOptions; role: keyof ResourceRole; label: string }[] = [
  { key: "primary_capability", role: "primary", label: "Primary" },
  { key: "secondary_capability", role: "secondary", label: "Secondary" },
  { key: "department", role: "department", label: "Department" },
  { key: "location", role: "location", label: "Location" },
  { key: "country", role: "country", label: "Country" },
  { key: "grade", role: "grade", label: "Grade" },
];

import type { CandidateHandlers } from "./CandidateActions";

export type { CandidateHandlers } from "./CandidateActions";

export function RoleTable({
  roles,
  options,
  candidates,
  mnhSlots = [],
  handlers,
  monthKeys = [],
  onChange,
  onAdd,
  onRemove,
  onSelect,
}: {
  roles: ResourceRole[];
  options: ProjectTrackFilterOptions;
  candidates: Candidate[];
  mnhSlots?: MnhStaffingSlot[];
  handlers: CandidateHandlers;
  /** Project timeline months (YYYY-MM-DD); used for candidate hour columns. */
  monthKeys?: string[];
  onChange: (id: string, patch: Partial<ResourceRole>) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
  onSelect: (roleId: string) => void;
}) {
  return (
    <TableCard
      title="Skill capabilities mix · Resourcing"
      count={`${roles.length} ${roles.length === 1 ? "role" : "roles"}`}
      description="Row filters flow into Resource Vision Pools when you click Select employee. Only confirmed allocations reduce availability."
      actions={
        <button type="button" className={primaryButtonClass} onClick={onAdd}>
          <Plus size={14} aria-hidden /> New resource role
        </button>
      }
    >
      <TableScroll label="Resource roles">
        <table className={`${tableClassDense} rv-role-table min-w-[72rem]`}>
          <thead>
            <tr>
              <th className={[tableHeadClass, "rv-role-table__index"].join(" ")}>#</th>
              {FILTER_COLUMNS.map((c) => (
                <th key={c.key} className={[tableHeadClass, "rv-role-table__filter-hd"].join(" ")}>
                  {c.label}
                </th>
              ))}
              <th className={tableHeadClass}>Required skills</th>
              <th className={tableHeadClass}>Status</th>
              <th className={tableHeadClass}>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role, idx) => {
              const mine = candidates.filter(
                (c) => c.position_id === role.id && !FINISHED.has(c.status),
              );
              const live = mine.filter((c) => !FINISHED.has(c.status));
              const mnhForRole = mnhSlots.filter(
                (s) => s.position_id === role.id && s.status === "Hiring from MNH",
              );
              const status = roleStatusForRole(
                live.map((c) => c.status),
                mnhForRole.length > 0,
              );
              return (
                <Fragment key={role.id}>
                  <tr className="rv-role-table__row">
                    <td className="rv-role-table__index tabular-nums text-muted">{idx + 1}</td>
                    {FILTER_COLUMNS.map((col) => (
                      <td key={col.key} className="rv-role-table__filter-cell">
                        <RoleFilterSelect
                          label={col.label}
                          rowIndex={idx}
                          value={String(role[col.role] ?? "")}
                          options={options[col.key]}
                          onChange={(v) => onChange(role.id, { [col.role]: v })}
                        />
                      </td>
                    ))}
                    <td className="max-w-[14rem]">
                      {role.skills.filter((s) => s.name.trim()).length ? (
                        <div className="flex flex-wrap gap-1">
                          {role.skills
                            .filter((s) => s.name.trim())
                            .map((s) => (
                              <span key={s.name} className="rv-soft-tag">
                                {s.name} · {s.level}
                              </span>
                            ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted">Set in pools</span>
                      )}
                    </td>
                    <td>
                      <CandidateStatusPill status={status} />
                    </td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <button type="button" className={primaryButtonClass} onClick={() => onSelect(role.id)}>
                          Select employee
                        </button>
                        {roles.length > 1 && live.length === 0 && mnhForRole.length === 0 ? (
                          <button
                            type="button"
                            className={quietButtonClass}
                            aria-label={`Remove role ${idx + 1}`}
                            onClick={() => onRemove(role.id)}
                          >
                            <Trash2 size={14} aria-hidden />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                  {mine.length > 0 || mnhForRole.length > 0 ? (
                    <tr className="rv-table-nested">
                      <td />
                      <td colSpan={FILTER_COLUMNS.length + 3} className="!py-3 !px-2">
                        {mnhForRole.length > 0 ? (
                          <RoleMnhSlotsTable slots={mnhForRole} role={role} monthKeys={monthKeys} />
                        ) : null}
                        {mine.length > 0 ? (
                          <RoleCandidatesTable
                            candidates={mine}
                            handlers={handlers}
                            role={role}
                            monthKeys={monthKeys}
                          />
                        ) : null}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </TableScroll>
    </TableCard>
  );
}
