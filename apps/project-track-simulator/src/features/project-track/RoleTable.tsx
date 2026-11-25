import { useMemo } from "react";

import type { Candidate, MnhStaffingSlot } from "../../api/staffing";
import type { ProjectTrackFilterOptions } from "../../api/staffingMeta";
import { primaryButtonClass } from "../../components/ui/primitives";
import { TableCard, TableScroll } from "../../components/ui/TableCard";
import { tableClassDense, tableHeadClass } from "../../components/ui/tableClasses";
import { roleStatusForRole } from "../../lib/candidateStatus";
import type { ResourceRole } from "../../lib/launch";
import { buildSections, roleFromFilters, sectionKeyForRole, sectionLabel } from "../../lib/roleCapabilityGroups";

import type { CandidateHandlers } from "./CandidateActions";
import { CandidateStatusPill } from "./CandidateStatus";
import { RoleCandidatesTable } from "./RoleCandidatesTable";
import { RoleFilterSelect } from "./RoleFilterSelect";
import { RoleMnhSlotsTable } from "./RoleMnhSlotsTable";

export type { CandidateHandlers } from "./CandidateActions";

const FILTER_COLUMNS: { key: keyof ProjectTrackFilterOptions; role: keyof ResourceRole; label: string }[] = [
  { key: "primary_capability", role: "primary", label: "Primary" },
  { key: "secondary_capability", role: "secondary", label: "Secondary" },
  { key: "department", role: "department", label: "Department" },
  { key: "location", role: "location", label: "Location" },
  { key: "country", role: "country", label: "Country" },
  { key: "grade", role: "grade", label: "Grade" },
];

/**
 * One filter row for the next selection, then one section per primary + secondary capability pair.
 * Everyone selected with the same pair is listed in that pair's section, one row per person, with
 * the filters they were selected with. A different pair starts a new section.
 */
export function RoleTable({
  draft,
  options,
  candidates,
  mnhSlots = [],
  handlers,
  monthKeys = [],
  onChange,
  onSelect,
}: {
  draft: ResourceRole;
  options: ProjectTrackFilterOptions;
  candidates: Candidate[];
  mnhSlots?: MnhStaffingSlot[];
  handlers: CandidateHandlers;
  /** Project timeline months (YYYY-MM-DD); used for candidate hour columns. */
  monthKeys?: string[];
  onChange: (patch: Partial<ResourceRole>) => void;
  onSelect: () => void;
}) {
  const sections = useMemo(() => buildSections(candidates, mnhSlots), [candidates, mnhSlots]);
  const target = sections.find((s) => s.key === sectionKeyForRole(draft));
  const draftSkills = draft.skills.filter((s) => s.name.trim());

  return (
    <TableCard
      title="Skill capabilities mix · Resourcing"
      count={`${sections.length} ${sections.length === 1 ? "section" : "sections"}`}
      description="Choose filters and click Select employee. People selected with the same primary and secondary capability are listed together in one section; a different pair starts a new section. Only confirmed allocations reduce availability."
    >
      <TableScroll label="Filters for the next selection">
        <table className={`${tableClassDense} rv-role-table min-w-[64rem]`}>
          <thead>
            <tr>
              {FILTER_COLUMNS.map((c) => (
                <th key={c.key} className={[tableHeadClass, "rv-role-table__filter-hd"].join(" ")}>
                  {c.label}
                </th>
              ))}
              <th className={tableHeadClass}>Required skills</th>
              <th className={tableHeadClass}>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="rv-role-table__row">
              {FILTER_COLUMNS.map((col) => (
                <td key={col.key} className="rv-role-table__filter-cell">
                  <RoleFilterSelect
                    label={col.label}
                    rowIndex={0}
                    value={String(draft[col.role] ?? "")}
                    options={options[col.key]}
                    onChange={(v) => onChange({ [col.role]: v })}
                  />
                </td>
              ))}
              <td className="max-w-[14rem]">
                {draftSkills.length ? (
                  <div className="flex flex-wrap gap-1">
                    {draftSkills.map((s) => (
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
                <button type="button" className={primaryButtonClass} onClick={onSelect}>
                  Select employee
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </TableScroll>

      <p className="rv-role-sections__target">
        {target ? (
          <>
            Selections join the <strong>{target.label}</strong> section.
          </>
        ) : (
          <>
            Selections start a new <strong>{sectionLabel(draft.primary, draft.secondary)}</strong> section.
          </>
        )}
      </p>

      {sections.length === 0 ? (
        <p className="rv-role-sections__empty">No one has been selected for this project yet.</p>
      ) : (
        <div className="rv-role-sections">
          {sections.map((section) => {
            const status = roleStatusForRole(
              section.candidates.map((c) => c.status),
              section.mnhSlots.length > 0,
            );
            const people = section.candidates.length;
            const slots = section.mnhSlots.length;
            return (
              <section key={section.key} className="rv-role-section" aria-label={`${section.label} section`}>
                <header className="rv-role-section__head">
                  <h3 className="rv-role-section__title">{section.label}</h3>
                  <span className="rv-role-section__meta">
                    {people} {people === 1 ? "resource" : "resources"}
                    {slots ? ` · ${slots} MyNextHire ${slots === 1 ? "slot" : "slots"}` : ""}
                  </span>
                  <CandidateStatusPill status={status} />
                </header>
                <div className="rv-role-section__body rv-scroll">
                  {people ? (
                    <RoleCandidatesTable
                      candidates={section.candidates}
                      handlers={handlers}
                      roleFor={(c) => roleFromFilters(c.demand_filters, c.position_id)}
                      monthKeys={monthKeys}
                    />
                  ) : null}
                  {slots ? (
                    <RoleMnhSlotsTable
                      slots={section.mnhSlots}
                      roleFor={(slot) => roleFromFilters(slot.demand_filters, slot.position_id)}
                      monthKeys={monthKeys}
                    />
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </TableCard>
  );
}
