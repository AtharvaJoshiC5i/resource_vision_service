const DIMENSIONS: [string, string][] = [
  ["Primary", "primary_capability"],
  ["Secondary", "secondary_capability"],
  ["Department", "department"],
  ["Location", "location"],
  ["Country", "country"],
  ["Grade", "grade"],
];

/** Role filters carried over from Project Track. Renders nothing when the role has none. */
export function PoolsInheritedBanner({
  filters,
  compact = false,
}: {
  filters?: Record<string, string[]>;
  compact?: boolean;
}) {
  const f = filters ?? {};
  const rows = DIMENSIONS.flatMap(([label, key]) => (f[key]?.length ? [{ label, value: f[key].join(", ") }] : []));
  if (rows.length === 0) return null;

  if (compact) {
    return (
      <div className="rv-pools-deck__row rv-pool-inherited rv-pool-inherited--compact" aria-label="Role filters">
        <span className="rv-pools-deck__rail">Role</span>
        <ul className="rv-pool-inherited__list">
          {rows.map((r) => (
            <li key={r.label} className="rv-pool-inherited__row">
              <span className="rv-pool-inherited__key">{r.label}</span>
              <span className="rv-pool-inherited__val">{r.value}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <section className="rv-pools-section rv-pool-inherited" aria-label="Role filters inherited from Project Track">
      <h3 className="rv-pools-section__title">Role filters</h3>
      <dl className="rv-pool-inherited__list">
        {rows.map((r) => (
          <div key={r.label} className="rv-pool-inherited__row">
            <dt>{r.label}</dt>
            <dd>{r.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}