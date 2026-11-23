import { useCallback, useEffect, useRef, useState } from "react";

/** Loads staffing-workflow data; refreshes on `reload()` and (optionally) on an interval. */
export function useStaffing<T>(load: () => Promise<T>, deps: readonly unknown[], pollMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  const run = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void run();
    if (!pollMs) return;
    const id = window.setInterval(() => void run(), pollMs);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, pollMs, run]);

  return { data, error, loading, reload: run };
}
