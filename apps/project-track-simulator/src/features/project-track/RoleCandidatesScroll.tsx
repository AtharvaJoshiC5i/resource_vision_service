import type { ReactNode } from "react";

import { useScrollChainWheel } from "../../hooks/useScrollChainWheel";
import { useScrollEdges } from "../../hooks/useScrollEdges";

/** Horizontal scroll for month columns only; pinned cells use `roleCandPin` classes. */
export function RoleCandidatesScroll({ children, label }: { children: ReactNode; label: string }) {
  const ref = useScrollEdges();
  useScrollChainWheel(ref);
  return (
    <div
      ref={ref}
      role="region"
      aria-label={label}
      className="rv-role-cand-scroll rv-scroll"
    >
      {children}
    </div>
  );
}