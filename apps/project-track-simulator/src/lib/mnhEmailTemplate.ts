import type { HiringRequestSubmit } from "./hiringRequest";
import { hiringFilterSummary } from "./hiringRequest";

export type MnhEmailDraft = {
  to: string;
  cc: string;
  subject: string;
  body_text: string;
  project_lead_name?: string;
  project_lead_email?: string | null;
  delivery_status?: string;
};

/** Client-side fallback when the preview API is unavailable. Keep in sync with `mnh_email.py`. */
export function buildMnhStaffingEmailLocal(
  request: HiringRequestSubmit,
  hrTo: string,
  defaultBuCc: string,
): MnhEmailDraft {
  const cc = (request.bu_lead_cc?.trim() || defaultBuCc).trim();
  const lead = (request.project_lead_name?.trim() || "Project lead").trim();
  const leadEmail = request.project_lead_email?.trim() ?? "";
  const timeline =
    request.start_date && request.end_date
      ? `${request.start_date.slice(0, 10)} to ${request.end_date.slice(0, 10)}`
      : "";
  const pool = request.pool_outcome;
  let poolNote = "";
  if (pool) {
    poolNote =
      pool.employees_total != null
        ? `The internal Resource Vision pool returned ${pool.employees_shown} employee(s) of ${pool.employees_total} ranked for this profile.`
        : `The internal Resource Vision pool returned ${pool.employees_shown} employee(s) for this profile.`;
  }
  const subject = `[MyNextHire] Staffing request · ${request.project_id} · ${request.capability} · ${request.headcount} FTE`;
  const criteria = hiringFilterSummary(request.filters);
  const skillLines =
    (request.required_skills ?? []).filter((s) => s.name.trim()).length > 0
      ? (request.required_skills ?? [])
          .filter((s) => s.name.trim())
          .map((s) => `  • ${s.name} (minimum level: ${s.level})`)
      : ["  • None specified"];

  const body_lines = [
    "Dear HR team,",
    "",
    `I am requesting external staffing support via MyNextHire for project ${request.project_id}.`,
    "",
    "── Request summary ──",
    `Capability / role family: ${request.capability}`,
    `Headcount requested: ${request.headcount}`,
    `Resource role (Project Track): ${request.position_id ?? "—"}`,
    `Project timeline: ${timeline || "—"}`,
    "",
    "── Role criteria (from Project Track) ──",
    ...(criteria.length
      ? criteria.map((r) => `  • ${r.label}: ${r.value}`)
      : ["  • No filters applied (Any on all dimensions)"]),
    "",
    "── Required skills ──",
    ...skillLines,
    "",
    "── Business justification ──",
    request.justification.trim(),
    "",
    ...(poolNote ? ["── Internal pool outcome ──", poolNote, ""] : []),
    "Please initiate sourcing through MyNextHire for the above profile.",
    "",
    "This message will be sent to HR with the BU lead copied when email delivery is enabled.",
    "",
    "Regards,",
    lead + (leadEmail ? ` (${leadEmail})` : ""),
  ];

  return {
    to: hrTo,
    cc,
    subject,
    body_text: body_lines.join("\n"),
    project_lead_name: lead,
    project_lead_email: leadEmail || null,
    delivery_status: "draft_only",
  };
}