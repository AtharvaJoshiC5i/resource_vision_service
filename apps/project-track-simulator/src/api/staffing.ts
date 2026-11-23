import { DEV_LAUNCH_TOKEN } from "../lib/launch";

import { staffingJson } from "./client";

export type CandidateStatus =
  | "New"
  | "Skills Matched"
  | "KB Pending"
  | "Training"
  | "Training Failed/Delayed"
  | "Interview Pending"
  | "Interview Booked"
  | "Expired"
  | "Rejected"
  | "Reserved"
  | "Confirmed"
  | "Released";

export type Candidate = {
  id: string;
  demand_id: string;
  project_id: string | null;
  position_id: string | null;
  employee_key: string;
  employee_code: string;
  employee_name: string;
  status: CandidateStatus;
  months: { month_key: string; hours: number }[];
};

export type Interview = {
  id: string;
  candidate_id: string;
  employee_key: string;
  project_id: string;
  status: "Booked" | "Expired" | "Passed" | "Rejected";
  booked_at: string;
  expires_at: string;
  outcome: string | null;
  rejection_type: string | null;
  rejection_reason: string | null;
};

export type KbRequest = {
  id: string;
  candidate_id: string;
  employee_key: string;
  project_id: string;
  status: "Sent" | "Training" | "Completed" | "Failed" | "Rejected";
  training_days: number;
  buffer_days: number;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  reason: string | null;
};

export type HiringRequest = {
  id: string;
  project_id: string;
  capability: string;
  headcount: number;
  justification: string;
  status: string;
  created_at: string;
  payload?: Record<string, unknown>;
};

export type MnhStaffingSlot = {
  id: string;
  hiring_request_id: string;
  project_id: string;
  position_id: string | null;
  slot_index: number;
  headcount_total: number;
  status: string;
  capability: string;
  created_at: string;
};

export type AuditEvent = {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
};

const post = <T,>(path: string, body: Record<string, unknown> = {}) =>
  staffingJson<T>(path, { method: "POST", body: JSON.stringify({ launch_token: DEV_LAUNCH_TOKEN, ...body }) });

const q = (project: string) => `project_id=${encodeURIComponent(project)}`;

export const staffingApi = {
  candidates: (project: string) => staffingJson<{ candidates: Candidate[] }>(`/candidates?${q(project)}`),
  interviews: (project: string) => staffingJson<{ interviews: Interview[] }>(`/interviews?${q(project)}`),
  kbRequests: (project: string) => staffingJson<{ requests: KbRequest[] }>(`/kb/requests?${q(project)}`),
  hiring: (project: string) => staffingJson<{ requests: HiringRequest[] }>(`/hiring-requests?${q(project)}`),
  workflow: (project: string) =>
    staffingJson<{
      candidates: Candidate[];
      interviews: Interview[];
      kb_requests: KbRequest[];
      hiring_requests: HiringRequest[];
      mnh_slots: MnhStaffingSlot[];
    }>(`/projects/${encodeURIComponent(project)}/workflow`),
  audit: () => staffingJson<{ events: AuditEvent[] }>("/audit?limit=200"),

  createDemand: (body: Record<string, unknown>) => post<{ demand_id: string }>("/demands", body),
  createCandidate: (demandId: string, employeeKey: string) =>
    post<{ candidate_id: string; block_slots_max?: number; active_blocks?: number }>("/candidates", {
      demand_id: demandId,
      employee_key: employeeKey,
    }),
  setHours: (candidateId: string, months: { month_key: string; hours: number }[]) =>
    staffingJson(`/candidates/${candidateId}/hours`, { method: "POST", body: JSON.stringify({ months }) }),
  action: (candidateId: string, action: "direct" | "kb" | "interview") =>
    post<{ status: string; warning?: string }>(`/candidates/${candidateId}/actions/${action}`),
  kbBatch: (demandId: string, candidateIds: string[]) =>
    post<{ status: string; warning?: string; request_id?: string; payload?: Record<string, unknown> }>(
      `/demands/${demandId}/kb-batch`,
      { candidate_ids: candidateIds },
    ),
  finalCheck: (candidateId: string) =>
    post<{ status: string; reservations: string[] }>(`/candidates/${candidateId}/final-check`),
  release: (candidateId: string) => post(`/candidates/${candidateId}/release`),
  interviewOutcome: (candidateId: string, outcome: "pass" | "reject", rejectionType?: string, reason?: string) =>
    post(`/candidates/${candidateId}/interview-outcome`, { outcome, rejection_type: rejectionType, reason }),
  trainingOutcome: (candidateId: string, outcome: "success" | "failed") =>
    post(`/candidates/${candidateId}/training-outcome`, { outcome }),
  requestHiring: (body: {
    project_id: string;
    capability: string;
    headcount: number;
    justification: string;
    start_date?: string;
    end_date?: string;
    position_id?: string;
    filters?: Record<string, string[]>;
    required_skills?: { name: string; level: string }[];
    month_hours?: { month_key: string; hours: number }[];
    pool_outcome?: { employees_shown: number; employees_total?: number };
    source?: string;
    bu_lead_cc?: string;
    project_lead_name?: string;
    project_lead_email?: string;
  }) => post<{ id: string; status: string; email_draft?: Record<string, unknown>; mnh_slots?: MnhStaffingSlot[] }>(
    "/hiring-requests",
    body,
  ),
  mnhEmailDefaults: () => staffingJson<{ hr_to: string; bu_lead_cc: string }>("/hiring-requests/email-defaults"),
  previewHiringEmail: (body: Record<string, unknown>) =>
    post<{
      email_draft: {
        to: string;
        cc: string;
        subject: string;
        body_text: string;
      };
      defaults: { hr_to: string; bu_lead_cc: string };
    }>("/hiring-requests/preview-email", body),
  fireEvent: (type: string, projectId: string, payload: Record<string, unknown> = {}) =>
    staffingJson("/events/project-track", {
      method: "POST",
      body: JSON.stringify({ type, project_id: projectId, payload }),
    }),
};
