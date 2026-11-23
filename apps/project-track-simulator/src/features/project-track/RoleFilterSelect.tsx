import { memo } from "react";

import { SelectField } from "../../components/ui/primitives";

/** Memoised: the page re-renders on every workflow refresh, but option lists rarely change. */
export const RoleFilterSelect = memo(function RoleFilterSelect({
  label,
  rowIndex,
  value,
  options,
  onChange,
}: {
  label: string;
  rowIndex: number;
  value: string;
  options: string[];
  onChange: (next: string) => void;
}) {
  const isAny = !value;
  return (
    <div className={["rv-role-filter", isAny ? "rv-role-filter--any" : "rv-role-filter--set"].join(" ")}>
      <SelectField
        controlSize="role"
        aria-label={`${label} for role ${rowIndex + 1}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Any</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </SelectField>
    </div>
  );
},
// onChange is recreated on every parent render but only calls a functional state update,
// so a stale closure is safe; skipping it keeps long option lists from re-rendering.
(prev, next) =>
  prev.value === next.value &&
  prev.options === next.options &&
  prev.label === next.label &&
  prev.rowIndex === next.rowIndex);
