import { ChevronRight, Database } from "lucide-react";

export function AppHeader({
  projectId,
  dataMode,
}: {
  projectId: string;
  dataMode: "azure" | "demo" | null;
}) {
  return (
    <header className="rv-app-header">
      <div className="rv-app-header__inner">
        <div className="flex min-w-0 items-center gap-3">
          <img src="/c5i-glyph.png" alt="" className="h-7 w-7 shrink-0 object-contain" />
          <span className="text-sm font-semibold tracking-[-0.011em] text-ink">Project Track</span>
          <span className="rv-app-header__divider" aria-hidden />
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-sm text-muted">
            <span className="hidden sm:inline">Projects</span>
            <ChevronRight aria-hidden className="hidden h-3.5 w-3.5 shrink-0 sm:inline" />
            <span aria-current="page" className="truncate font-medium text-ink-soft">
              {projectId || "Untitled"}
            </span>
          </nav>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {dataMode ? (
            <span className={`rv-env-badge ${dataMode === "demo" ? "rv-env-badge--demo" : ""}`}>
              <Database aria-hidden className="h-3.5 w-3.5" />
              {dataMode === "demo" ? "Demo data" : "Live data"}
            </span>
          ) : null}
          <span className="rv-avatar" aria-label="Signed in as Simulator Lead" title="Simulator Lead">
            SL
          </span>
        </div>
      </div>
    </header>
  );
}
