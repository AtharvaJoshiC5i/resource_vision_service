import type { LucideIcon } from "lucide-react";

export type StatTone = "primary" | "warning" | "success" | "neutral";

export type Stat = { label: string; value: number; caption?: string; icon: LucideIcon; tone?: StatTone };

/** One framed row of headline figures, separated by hairlines. */
export function StatStrip({ stats, label }: { stats: Stat[]; label: string }) {
  return (
    <section className="rv-stat-strip rv-frame" aria-label={label}>
      <dl className="rv-stat-strip__grid" style={{ "--rv-stat-cols": stats.length } as React.CSSProperties}>
        {stats.map((s) => (
          <div key={s.label} className="rv-stat">
            <dt className="rv-stat__label">
              <span className={`rv-stat__icon rv-stat__icon--${s.tone ?? "neutral"}`} aria-hidden>
                <s.icon className="h-3.5 w-3.5" strokeWidth={2} />
              </span>
              {s.label}
            </dt>
            <dd className="rv-stat__value">{s.value.toLocaleString("en-US")}</dd>
            {s.caption ? <dd className="rv-stat__caption">{s.caption}</dd> : null}
          </div>
        ))}
      </dl>
    </section>
  );
}
