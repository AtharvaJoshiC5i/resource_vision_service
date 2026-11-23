import { useState } from "react";
import { ChevronDown } from "lucide-react";

import type { PoolEmployee } from "./types";

const OTHER_PREVIEW = 6;

function levelLabel(level: string | null | undefined): string {
  if (!level || level === "NOT_DOCUMENTED") return "Not documented";
  return level;
}

type Tick = PoolEmployee["skill_ticks"][number];

function SkillMatchChip({ tick }: { tick: Tick }) {
  const need = levelLabel(tick.required_level);
  const has = tick.current_level ? levelLabel(tick.current_level) : null;
  const current = has ?? "Not in DB";
  const title = tick.matched
    ? `${tick.skill}: ${current} meets required ${need}`
    : has
      ? `${tick.skill}: has ${current}, need ${need}`
      : `${tick.skill}: not on profile; need ${need}`;

  return (
    <li
      className={`rv-pool-skill-chip ${tick.matched ? "rv-pool-skill-chip--ok" : "rv-pool-skill-chip--gap"}`}
      title={title}
    >
      <span className="rv-pool-skill-chip__mark" aria-hidden>
        {tick.matched ? "✓" : "✗"}
      </span>
      <span className="rv-pool-skill-chip__name">{tick.skill}</span>
      <span className="rv-pool-skill-chip__level">{current}</span>
      {!tick.matched ? <span className="rv-pool-skill-chip__need">need {need}</span> : null}
    </li>
  );
}

function ProfileSkillTag({ name, level }: { name: string; level: string }) {
  return (
    <li className="rv-skill-tag" title={`${name}: ${levelLabel(level)}`}>
      <span className="rv-skill-tag__name">{name}</span>
      <span className="rv-skill-tag__level">{levelLabel(level)}</span>
    </li>
  );
}

export function PoolSkillsCell({ row }: { row: PoolEmployee }) {
  const [otherExpanded, setOtherExpanded] = useState(false);
  const ticks = row.skill_ticks ?? [];
  const profile = row.skills ?? [];
  const required = new Set(ticks.map((t) => t.skill.toLowerCase()));
  const others = profile.filter((s) => !required.has(s.name.toLowerCase()));
  const matched = ticks.filter((t) => t.matched).length;
  const filtering = ticks.length > 0;

  if (!ticks.length && !profile.length) {
    return <span className="rv-pool-skills-empty">No skills on record</span>;
  }

  const otherPreview = otherExpanded ? others : others.slice(0, OTHER_PREVIEW);
  const otherHidden = !otherExpanded && others.length > OTHER_PREVIEW;

  return (
    <div className={`rv-skills ${filtering ? "rv-skills--filtered" : ""}`}>
      {filtering ? (
        <section aria-label="Required skills match">
          <div
            className={`rv-pool-skill-match ${matched === ticks.length ? "rv-pool-skill-match--full" : ""}`}
            role="status"
          >
            <span className="rv-pool-skill-match__label">
              {matched === ticks.length
                ? "All required skills met"
                : `${matched} of ${ticks.length} skills matched`}
            </span>
          </div>
          <ul className="rv-pool-skill-chips" aria-label="Required skills">
            {ticks.map((t) => (
              <SkillMatchChip key={t.skill} tick={t} />
            ))}
          </ul>
        </section>
      ) : (
        <section aria-label="Skills on record">
          <p className="rv-pool-skills-empty rv-pool-skills-empty--hint">Add required skills above to compare match.</p>
          <ul className="rv-skills__tags">
            {profile.map((s) => (
              <ProfileSkillTag key={s.name} name={s.name} level={s.level} />
            ))}
          </ul>
        </section>
      )}

      {filtering && others.length > 0 ? (
        <section aria-label="Other skills" className="rv-skills__others-compact">
          {otherHidden ? (
            <button
              type="button"
              className="rv-skill-more"
              aria-expanded={otherExpanded}
              onClick={() => setOtherExpanded(true)}
            >
              {others.length - OTHER_PREVIEW} more on profile ({others.length} total)
              <ChevronDown size={11} aria-hidden />
            </button>
          ) : null}
          <ul className="rv-skills__tags">
            {otherPreview.map((s) => (
              <ProfileSkillTag key={s.name} name={s.name} level={s.level} />
            ))}
          </ul>
          {otherExpanded && others.length > OTHER_PREVIEW ? (
            <button
              type="button"
              className="rv-skill-more"
              aria-expanded
              onClick={() => setOtherExpanded(false)}
            >
              Show fewer
              <ChevronDown size={11} aria-hidden className="rotate-180" />
            </button>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}