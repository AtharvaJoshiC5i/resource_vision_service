import { useCallback, useState } from "react";

import { staffingApi } from "../api/staffing";

import { useStaffing } from "./useStaffing";

/** All staffing-workflow data for one project: one combined request every few seconds. */
export function useProjectWorkflow(projectId: string) {
  const workflow = useStaffing(() => staffingApi.workflow(projectId), [projectId], 5000);
  const audit = useStaffing(() => staffingApi.audit(), [projectId], 15000);

  const reloadAll = useCallback(async () => {
    await Promise.all([workflow.reload(), audit.reload()]);
  }, [workflow, audit]);

  return {
    candidates: workflow.data?.candidates ?? [],
    interviews: workflow.data?.interviews ?? [],
    kbRequests: workflow.data?.kb_requests ?? [],
    hiringRequests: workflow.data?.hiring_requests ?? [],
    mnhSlots: workflow.data?.mnh_slots ?? [],
    audit: audit.data?.events ?? [],
    error: workflow.error,
    loading: workflow.loading,
    reloadAll,
  };
}

/** Runs one workflow action with a busy flag and a user-facing message. */
export function useActionRunner(reload: () => Promise<void>, report: (message: string) => void) {
  const [busy, setBusy] = useState<string | null>(null);
  const run = useCallback(
    async (key: string, label: string, fn: () => Promise<unknown>) => {
      setBusy(key);
      try {
        await fn();
        report(`${label} done.`);
      } catch (e) {
        report(`${label} failed: ${e instanceof Error ? e.message : "request failed"}`);
      } finally {
        setBusy(null);
        try {
          await reload();
        } catch {
          /* polling failed — action may still have succeeded */
        }
      }
    },
    [reload, report],
  );
  return { busy, run };
}
