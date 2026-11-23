"""MyNextHire staffing request email draft (HR To, BU lead CC). Sending is not wired yet."""

from __future__ import annotations

from app.config import get_settings


def _filter_lines(filters: dict | None) -> list[str]:
    labels = {
        "primary_capability": "Primary capability",
        "secondary_capability": "Secondary capability",
        "department": "Department",
        "location": "Location",
        "country": "Country",
        "grade": "Grade",
    }
    lines: list[str] = []
    for key, label in labels.items():
        vals = (filters or {}).get(key) or []
        if vals:
            lines.append(f"  • {label}: {', '.join(str(v) for v in vals)}")
    return lines


def _skill_lines(skills: list[dict] | None) -> list[str]:
    if not skills:
        return ["  • None specified"]
    return [f"  • {s.get('name', '').strip()} (minimum level: {s.get('level', '—')})" for s in skills if s.get("name")]


def build_staffing_email(
    *,
    project_id: str,
    capability: str,
    headcount: int,
    justification: str,
    start_date: str | None = None,
    end_date: str | None = None,
    position_id: str | None = None,
    filters: dict | None = None,
    required_skills: list[dict] | None = None,
    pool_outcome: dict | None = None,
    bu_lead_cc: str | None = None,
    project_lead_name: str | None = None,
    project_lead_email: str | None = None,
) -> dict:
    settings = get_settings()
    hr_to = settings.mnh_hr_to
    cc = (bu_lead_cc or "").strip() or settings.mnh_bu_lead_cc_default
    lead = (project_lead_name or "Project lead").strip()
    lead_email = (project_lead_email or "").strip()

    timeline = ""
    if start_date and end_date:
        timeline = f"{start_date[:10]} to {end_date[:10]}"

    pool_note = ""
    if pool_outcome is not None:
        shown = pool_outcome.get("employees_shown", 0)
        total = pool_outcome.get("employees_total")
        if total is not None:
            pool_note = f"The internal Resource Vision pool returned {shown} employee(s) of {total} ranked for this profile."
        else:
            pool_note = f"The internal Resource Vision pool returned {shown} employee(s) for this profile."

    subject = f"[MyNextHire] Staffing request · {project_id} · {capability} · {headcount} FTE"

    body_lines = [
        "Dear HR team,",
        "",
        f"I am requesting external staffing support via MyNextHire for project {project_id}.",
        "",
        "── Request summary ──",
        f"Capability / role family: {capability}",
        f"Headcount requested: {headcount}",
        f"Resource role (Project Track): {position_id or '—'}",
        f"Project timeline: {timeline or '—'}",
        "",
        "── Role criteria (from Project Track) ──",
        *(_filter_lines(filters) or ["  • No filters applied (Any on all dimensions)"]),
        "",
        "── Required skills ──",
        *_skill_lines(required_skills),
        "",
        "── Business justification ──",
        justification.strip(),
        "",
    ]
    if pool_note:
        body_lines.extend(["── Internal pool outcome ──", pool_note, ""])
    body_lines.extend(
        [
            "Please initiate sourcing through MyNextHire for the above profile.",
            "",
            "This message will be sent to HR with the BU lead copied when email delivery is enabled.",
            "",
            f"Regards,",
            lead + (f" ({lead_email})" if lead_email else ""),
        ]
    )
    body_text = "\n".join(body_lines)

    return {
        "to": hr_to,
        "cc": cc,
        "subject": subject,
        "body_text": body_text,
        "project_lead_name": lead,
        "project_lead_email": lead_email or None,
        "delivery_status": "draft_only",
    }