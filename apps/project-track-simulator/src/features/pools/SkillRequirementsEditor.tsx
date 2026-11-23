import { useMemo, useState } from "react";
import { Plus, X } from "lucide-react";

import {
  SelectField,
  buttonClass,
  fieldClass,
  labelClass,
  primaryButtonClass,
} from "../../components/ui/primitives";

import { SkillNameCombobox } from "./SkillNameCombobox";

export type SkillRow = { name: string; level: string };

const DEFAULT_LEVELS = ["Foundational", "Applied", "Advanced", "Expert"] as const;

function SkillPill({
  name,
  level,
  levels,
  onLevel,
  onRemove,
}: {
  name: string;
  level: string;
  levels: string[];
  onLevel: (level: string) => void;
  onRemove: () => void;
}) {
  const levelValue = levels.includes(level) ? level : levels[0] ?? level;
  return (
    <li className="rv-skill-pill">
      <span className="rv-skill-pill__name" title={name}>
        {name}
      </span>
      <SelectField
        controlSize="pill"
        value={levelValue}
        onChange={(e) => onLevel(e.target.value)}
        aria-label={`Minimum level for ${name}`}
      >
        {levels.map((lv) => (
          <option key={lv} value={lv}>
            {lv}
          </option>
        ))}
      </SelectField>
      <button
        type="button"
        className="rv-skill-pill__remove"
        aria-label={`Remove ${name}`}
        onClick={onRemove}
      >
        <X size={13} aria-hidden />
      </button>
    </li>
  );
}

export function SkillRequirementsEditor({
  skills,
  levels,
  names = [],
  catalogLoading = false,
  compact = false,
  onChange,
}: {
  skills: SkillRow[];
  levels: string[];
  names?: string[];
  catalogLoading?: boolean;
  compact?: boolean;
  onChange: (next: SkillRow[]) => void;
}) {
  const rankedLevels = useMemo(() => (levels.length ? levels : [...DEFAULT_LEVELS]), [levels]);
  const committed = skills.filter((s) => s.name.trim());
  const [draftName, setDraftName] = useState("");
  const [pickedLevel, setDraftLevel] = useState(() => rankedLevels[0] ?? "Applied");
  const draftLevel = rankedLevels.includes(pickedLevel) ? pickedLevel : (rankedLevels[0] ?? "Applied");

  const taken = useMemo(() => new Set(committed.map((s) => s.name.trim().toLowerCase())), [committed]);
  const catalog = useMemo(() => names.filter((n) => n.trim()), [names]);
  const suggestNames = useMemo(
    () => catalog.filter((n) => !taken.has(n.trim().toLowerCase())),
    [catalog, taken],
  );

  const resolveSkillName = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) return "";
    const hit = catalog.find((n) => n.trim().toLowerCase() === trimmed.toLowerCase());
    return hit ?? trimmed;
  };

  const draftTrimmed = draftName.trim();
  const canAdd = Boolean(draftTrimmed) && !taken.has(draftTrimmed.toLowerCase());

  const commitDraft = () => {
    const name = resolveSkillName(draftName);
    if (!name || taken.has(name.toLowerCase())) return;
    if (!rankedLevels.includes(draftLevel)) return;
    const key = name.toLowerCase();
    const withoutDup = committed.filter((s) => s.name.trim().toLowerCase() !== key);
    onChange([...withoutDup, { name, level: draftLevel }]);
    setDraftName("");
  };

  const updateLevel = (i: number, level: string) => {
    if (!rankedLevels.includes(level)) return;
    const next = [...committed];
    next[i] = { ...next[i], level };
    onChange(next);
  };

  const remove = (i: number) => onChange(committed.filter((_, idx) => idx !== i));

  const catalogEmpty = !catalogLoading && catalog.length === 0;
  const hint =
    "Type a skill (catalog suggestions while typing). Minimum level uses Foundational → Expert.";
  const shellClass = compact ? "rv-pools-deck__row rv-pool-skills rv-pool-skills--compact" : "rv-pool-skills";
  const label = compact ? "sr-only" : labelClass;
  const draftField = compact ? `${fieldClass} rv-deck-field` : fieldClass;

  return (
    <section
      className={shellClass}
      aria-labelledby="rv-pool-skills-heading"
      title={compact ? hint : undefined}
    >
      {compact ? (
        <h3 id="rv-pool-skills-heading" className="rv-pools-deck__rail">
          Skills
        </h3>
      ) : (
        <div className="rv-pool-skills__header">
          <h3 id="rv-pool-skills-heading" className="text-sm font-medium text-ink" title={hint}>
            Required skills
          </h3>
          {committed.length > 0 ? (
            <span className="rv-soft-tag shrink-0 tabular-nums">
              {committed.length} {committed.length === 1 ? "skill" : "skills"}
            </span>
          ) : null}
        </div>
      )}

      <div className="rv-pool-skills__body">
        {committed.length > 0 ? (
          <ul className="rv-skill-pill-list">
            {committed.map((row, i) => (
              <SkillPill
                key={`${row.name}-${i}`}
                name={row.name}
                level={row.level}
                levels={rankedLevels}
                onLevel={(lv) => updateLevel(i, lv)}
                onRemove={() => remove(i)}
              />
            ))}
          </ul>
        ) : compact ? null : (
          <p className="rv-pool-skills__empty">No skills yet — enter a name and minimum level below.</p>
        )}

        <form
          className={`rv-skill-composer ${compact ? "rv-skill-composer--compact" : ""}`}
          onSubmit={(ev) => {
            ev.preventDefault();
            commitDraft();
          }}
        >
          <label className="rv-skill-composer__field min-w-0">
            <span className={label}>Skill name</span>
            <SkillNameCombobox
              value={draftName}
              onChange={setDraftName}
              suggestions={suggestNames}
              disabled={catalogLoading}
              placeholder={catalogLoading ? "Loading…" : "Skill name, e.g. Python"}
              inputClassName={draftField}
            />
          </label>
          <label className="rv-skill-composer__field rv-skill-composer__field--level min-w-0">
            <span className={label}>Minimum level</span>
            <SelectField
              className={compact ? "rv-deck-select" : ""}
              aria-label="Minimum proficiency level"
              value={draftLevel}
              onChange={(ev) => setDraftLevel(ev.target.value)}
            >
              {rankedLevels.map((lv) => (
                <option key={lv} value={lv}>
                  {lv}
                </option>
              ))}
            </SelectField>
          </label>
          <button
            type="submit"
            className={[
              canAdd ? primaryButtonClass : buttonClass,
              compact ? "rv-skill-composer__add rv-deck-btn" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            disabled={!canAdd}
            aria-disabled={!canAdd}
          >
            <Plus size={14} strokeWidth={2} aria-hidden />
            {compact ? <span className="rv-skill-composer__add-text">Add</span> : "Add skill"}
          </button>
        </form>
      </div>

      {catalogEmpty && !compact ? (
        <p className="rv-pool-skills__catalog-hint" role="status">
          Catalog suggestions unavailable — spell skill names as they appear on employee records.
        </p>
      ) : null}
    </section>
  );
}