import type { ReactNode } from "react";
import { CalendarRange, Hash, Timer } from "lucide-react";

import { shortDate } from "../../lib/format";

export type HeroTab<T extends string> = { value: T; label: string; count?: number };

export function ProjectHero<T extends string>({
  proposal,
  projectId,
  startDate,
  endDate,
  months,
  tabs,
  tab,
  onTab,
  actions,
}: {
  proposal: string;
  projectId: string;
  startDate: string;
  endDate: string;
  months: number;
  tabs: HeroTab<T>[];
  tab: T;
  onTab: (next: T) => void;
  actions?: ReactNode;
}) {
  return (
    <section className="rv-hero rv-frame" aria-labelledby="rv-hero-title">
      <div className="rv-hero__body">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 id="rv-hero-title" className="rv-hero__title">
              {proposal}
            </h1>
            <span className="rv-status-badge rv-status-badge--success">
              <span aria-hidden className="rv-status-badge__dot" />
              Confirmed
            </span>
          </div>
          <dl className="rv-hero__meta">
            <div>
              <dt className="sr-only">Project ID</dt>
              <dd>
                <Hash aria-hidden />
                {projectId || "–"}
              </dd>
            </div>
            <div>
              <dt className="sr-only">Project window</dt>
              <dd>
                <CalendarRange aria-hidden />
                {shortDate(startDate)} – {shortDate(endDate)}
              </dd>
            </div>
            <div>
              <dt className="sr-only">Duration</dt>
              <dd>
                <Timer aria-hidden />
                {months} {months === 1 ? "month" : "months"}
              </dd>
            </div>
          </dl>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      <nav className="rv-tabs" aria-label="Project sections">
        {tabs.map((t) => (
          <button
            key={t.value}
            type="button"
            className="rv-tabs__tab"
            aria-current={t.value === tab ? "page" : undefined}
            onClick={() => onTab(t.value)}
          >
            {t.label}
            {t.count ? <span className="rv-tabs__count">{t.count}</span> : null}
          </button>
        ))}
      </nav>
    </section>
  );
}
