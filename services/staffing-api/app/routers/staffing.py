from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.database import DatabaseError
from app import orchestrator
from app.ports import get_ports
from app.rv import service as rv_service
from app.schemas import (
    CandidateAction,
    CandidateCreate,
    CandidateHours,
    DemandCreate,
    HiringRequestCreate,
    InterviewOutcome,
    KbBatchAction,
    LaunchValidate,
    PoolSearchRequest,
    ProjectTrackEvent,
    TrainingOutcome,
)
from app.services.capability_group import capability_group_key_from_filters
from app.services.employee_blocks import EmployeeBlockLimitError, create_candidate_with_block
from app.services.events import handle_project_event
from app.services.mnh_email import build_staffing_email
from app.services.pool_service import _data_sources, search_pool, skill_vocabulary
from app.runtime import runtime_info as build_runtime_info
from app.services.reconcile import reconcile
from app.services.snapshot import get_availability_snapshot
from app.staffing_store import get_staffing_store, serialize
from app.workers.outbox import publish_pending
from rv_availability import engine as e
from rv_availability import views as v
from rv_availability.staffing.launch_filters import dedupe_options

router = APIRouter(prefix="/api/staffing", tags=["staffing"])


def _identity(launch_token: str) -> dict:
    settings = get_settings()
    ports = get_ports(settings.dev_launch_token)
    try:
        return ports.identity.resolve(launch_token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _actor(launch_token: str) -> str:
    return str(_identity(launch_token)["user_id"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/runtime")
def staffing_runtime():
    """Active data switch (from RV_DATA_MODE / RV_DATA_SOURCE). Restart API after changing .env."""
    return build_runtime_info()


@router.get("/meta")
def staffing_meta():
    try:
        snap = get_availability_snapshot()
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail="The data source is currently unavailable.") from error
    opts = v.availability_options(snap)
    for dim in ("capabilities", "secondary_capabilities", "departments", "locations", "countries", "grades"):
        opts[dim] = dedupe_options(opts.get(dim) or [])
    settings = get_settings()
    data = rv_service.data_info()
    return {
        "window": snap.window,
        "capacity_hours": e.CAPACITY_HOURS,
        "options": opts,
        "skill_level_order": settings.skill_levels(),
        "skills": skill_vocabulary(get_ports(settings.dev_launch_token), settings.skill_levels()),
        "data": data,
        "data_sources": _data_sources(),
        "runtime": build_runtime_info(),
        "employee_block_max": settings.employee_block_max,
    }


@router.get("/filters")
def staffing_filters():
    """Role filter options for the Project Track page. Reads only the availability snapshot,
    never the skills view, so the filters are ready as soon as availability is."""
    try:
        snap = get_availability_snapshot()
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail="The data source is currently unavailable.") from error
    opts = v.availability_options(snap)
    return {
        "options": {
            dim: dedupe_options(opts.get(dim) or [])
            for dim in ("capabilities", "secondary_capabilities", "departments", "locations", "countries", "grades")
        },
        "runtime": build_runtime_info(),
    }


@router.get("/skills/vocabulary")
def staffing_skill_vocabulary():
    """Skill names and levels from the skills view (pool skill editor)."""
    settings = get_settings()
    return {
        "skill_level_order": settings.skill_levels(),
        "skills": skill_vocabulary(get_ports(settings.dev_launch_token), settings.skill_levels()),
    }


@router.get("/sources")
def staffing_sources():
    return {"data_sources": _data_sources()}


@router.post("/pools/search")
def pools_search(body: PoolSearchRequest):
    settings = get_settings()
    ports = get_ports(settings.dev_launch_token)
    store = get_staffing_store()
    if body.launch_token:
        _actor(body.launch_token)
    try:
        return search_pool(store, body.model_dump(), settings.skill_levels(), ports)
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/availability/employee/{key}")
def employee_availability(key: str):
    try:
        snap = get_availability_snapshot()
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    emp = snap.employees.get(key.upper())
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    from rv_availability.staffing.month_view import staffing_month_view

    months = []
    for m in snap.window:
        em = snap.employee_months.get((emp.key, m))
        view = staffing_month_view(em, emp)
        months.append(
            {
                "month": m,
                "status": view.status,
                "remaining": view.remaining,
                "planned": view.planned,
                "bookable_hours": view.bookable_hours,
                "status_source": view.source,
            }
        )
    return {"employee": {"key": emp.key, "code": emp.code, "name": emp.name}, "months": months}


def _demand_or_404(store, demand_id: str):
    demand = store.get_demand(demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    return demand


def _candidate_bundle(store, candidate_id: str):
    c = store.get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c, _demand_or_404(store, c.demand_id)


def _candidates_json(store, candidates, project_id: str | None = None) -> list[dict]:
    """Candidate dicts enriched with employee name/code and the owning project / role."""
    demands = {d.id: d for d in store.list_demands(project_id)}
    try:
        people = {k: (e.code, e.name) for k, e in get_availability_snapshot().employees.items()}
    except DatabaseError:
        people = {}
    out = []
    for c in candidates:
        d = demands.get(c.demand_id)
        code, name = people.get(c.employee_key.upper(), (c.employee_key, c.employee_key))
        filters = d.filters_json if d else {}
        demand_filters = {k: v for k, v in (filters or {}).items() if not str(k).startswith("_")}
        cap_key = capability_group_key_from_filters(demand_filters)
        out.append(
            {
                "id": c.id,
                "demand_id": c.demand_id,
                "project_id": d.project_id if d else None,
                "position_id": d.position_id if d else None,
                "capability_group_key": cap_key,
                "demand_filters": demand_filters,
                "required_skills": (d.required_skills_json if d else None) or [],
                "employee_key": c.employee_key,
                "employee_code": code,
                "employee_name": name,
                "status": c.status,
                "months": [{"month_key": m.month_key, "hours": m.hours} for m in c.months],
            }
        )
    return out


def _mnh_slots_json(store, project_id: str) -> list[dict]:
    hiring = {h.id: h for h in store.list_hiring_requests(project_id)}
    out: list[dict] = []
    for s in store.list_mnh_slots(project_id=project_id):
        row = serialize(s)
        h = hiring.get(s.hiring_request_id)
        payload = h.payload if h else {}
        ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        filters = ctx.get("filters") or payload.get("filters") or {}
        row["capability_group_key"] = capability_group_key_from_filters(filters)
        row["demand_filters"] = filters
        out.append(row)
    return out


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/launch/validate")
def validate_launch(body: LaunchValidate):
    ports = get_ports(get_settings().dev_launch_token)
    try:
        return {"valid": True, "identity": ports.identity.resolve(body.launch_token)}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/demands")
def create_demand(body: DemandCreate):
    actor = _actor(body.launch_token)
    settings = get_settings()
    status = (body.project_status or "confirmed").strip().lower()
    if status not in settings.confirmed_statuses():
        raise HTTPException(status_code=409, detail=f"Project status {status!r} is not confirmed; staffing is not allowed")
    try:
        orchestrator.validate_demand_window(body.start_date, body.end_date)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    store = get_staffing_store()
    row = store.create_demand(
        project_id=body.project_id,
        proposal_number=body.proposal_number,
        sub_project_name=body.sub_project_name,
        position_id=body.position_id,
        start_date=body.start_date,
        end_date=body.end_date,
        filters_json=body.filters,
        required_skills_json=body.required_skills,
        created_by=actor,
    )
    store.insert_audit(actor, "create_demand", "demand", row.id, {"project_id": body.project_id})
    return {"demand_id": row.id}


@router.get("/demands")
def list_demands(project_id: str | None = None):
    store = get_staffing_store()
    return {"demands": [serialize(d) for d in store.list_demands(project_id)]}


@router.get("/demands/{demand_id}")
def get_demand(demand_id: str):
    store = get_staffing_store()
    demand = _demand_or_404(store, demand_id)
    data = serialize(demand)
    data["candidates"] = _candidates_json(store, store.list_candidates(demand_id=demand_id))
    return data


@router.post("/candidates")
def create_candidate(body: CandidateCreate):
    settings = get_settings()
    identity = _identity(body.launch_token)
    store = get_staffing_store()
    demand = _demand_or_404(store, body.demand_id)
    actor = str(identity["user_id"])
    display = str(identity.get("display_name") or actor)
    try:
        c, block = create_candidate_with_block(
            store,
            demand,
            body.employee_key,
            actor,
            display,
            settings.employee_block_max,
        )
    except EmployeeBlockLimitError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "employee_block_limit",
                "message": f"This resource already has {exc.max_slots} active selections.",
                "max_slots": exc.max_slots,
                "active_blocks": exc.holders,
            },
        ) from exc
    store.insert_audit(actor, "block_employee", "candidate", c.id, {"employee_key": body.employee_key})
    return {
        "candidate_id": c.id,
        "status": c.status,
        "block_id": block.id,
        "active_blocks": len(store.list_active_blocks_for_employee(body.employee_key)),
        "block_slots_max": settings.employee_block_max,
    }


@router.get("/candidates")
def list_candidates(project_id: str | None = None, demand_id: str | None = None):
    store = get_staffing_store()
    return {"candidates": _candidates_json(store, store.list_candidates(demand_id, project_id), project_id)}


@router.get("/projects/{project_id}/workflow")
def project_workflow(project_id: str):
    """Everything the Project Track page polls, in one request on one pooled connection."""
    store = get_staffing_store()
    orchestrator.expire_interviews(store)
    return {
        "candidates": _candidates_json(store, store.list_candidates(project_id=project_id), project_id),
        "interviews": [serialize(i) for i in store.list_interviews(project_id)],
        "kb_requests": [serialize(r) for r in store.list_kb_requests(project_id)],
        "hiring_requests": [serialize(h) for h in store.list_hiring_requests(project_id)],
        "mnh_slots": _mnh_slots_json(store, project_id),
    }


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str):
    store = get_staffing_store()
    c, _ = _candidate_bundle(store, candidate_id)
    return _candidates_json(store, [c])[0]


@router.post("/candidates/{candidate_id}/hours")
def set_hours(candidate_id: str, body: CandidateHours):
    store = get_staffing_store()
    c, demand = _candidate_bundle(store, candidate_id)
    try:
        c = orchestrator.set_candidate_hours(
            store,
            c,
            demand,
            [m.model_dump() for m in body.months],
            allow_window_extend=get_settings().allow_window_extend,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return {"candidate_id": c.id, "months": len(c.months)}


@router.post("/candidates/{candidate_id}/actions/{action}")
def candidate_action(candidate_id: str, action: str, body: CandidateAction):
    settings = get_settings()
    ports = get_ports(settings.dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    c, demand = _candidate_bundle(store, candidate_id)
    if action not in {"direct", "kb", "interview"}:
        raise HTTPException(status_code=400, detail="Unknown action")
    if not c.months:
        raise HTTPException(status_code=400, detail="Set month hours first")
    orchestrator.expire_interviews(store)

    if action == "direct":
        result = orchestrator.action_direct(store, c, ports)
    elif action == "kb":
        result = orchestrator.action_kb(store, c, demand, ports, settings.training_ratio, settings.skill_levels())
    else:
        result = orchestrator.action_interview(store, c, ports, settings.interview_expiry_days)

    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    store.insert_audit(actor, f"select_{action}", "candidate", c.id, {"status": result.get("status")})
    return result


@router.post("/demands/{demand_id}/kb-batch")
def demand_kb_batch(demand_id: str, body: KbBatchAction):
    settings = get_settings()
    ports = get_ports(settings.dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    demand = store.get_demand(demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    if not body.candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids is required")

    candidates = []
    for cid in body.candidate_ids:
        c, cand_demand = _candidate_bundle(store, cid)
        if cand_demand.id != demand_id:
            raise HTTPException(status_code=400, detail=f"Candidate {cid} is not on this demand")
        if not c.months:
            raise HTTPException(status_code=400, detail=f"Set month hours for candidate {cid} first")
        candidates.append(c)

    orchestrator.expire_interviews(store)
    result = orchestrator.action_kb_batch(
        store, demand, candidates, ports, settings.training_ratio, settings.skill_levels()
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    for c in candidates:
        store.insert_audit(actor, "select_kb_batch", "candidate", c.id, {"status": result.get("status")})
    return result


@router.post("/candidates/{candidate_id}/interview-outcome")
def candidate_interview_outcome(candidate_id: str, body: InterviewOutcome):
    ports = get_ports(get_settings().dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    c, _ = _candidate_bundle(store, candidate_id)
    result = orchestrator.interview_outcome(store, c, body.outcome, ports, body.rejection_type, body.reason)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    store.insert_audit(actor, f"interview_{body.outcome.lower()}", "candidate", c.id, {"reason": body.reason})
    return result


@router.post("/candidates/{candidate_id}/training-outcome")
def candidate_training_outcome(candidate_id: str, body: TrainingOutcome):
    ports = get_ports(get_settings().dev_launch_token)
    actor = _actor(body.launch_token)
    outcome = body.outcome.lower()
    if outcome not in {"success", "failed"}:
        raise HTTPException(status_code=400, detail="outcome must be 'success' or 'failed'")
    store = get_staffing_store()
    c, _ = _candidate_bundle(store, candidate_id)
    result = orchestrator.training_outcome(store, c, outcome == "success", ports, body.reason)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    store.insert_audit(actor, f"training_{outcome}", "candidate", c.id, {})
    return result


@router.post("/candidates/{candidate_id}/release")
def candidate_release(candidate_id: str, body: CandidateAction):
    ports = get_ports(get_settings().dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    c, _ = _candidate_bundle(store, candidate_id)
    result = orchestrator.release_candidate(store, c, actor, ports)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/candidates/{candidate_id}/final-check")
def candidate_final_check(candidate_id: str, body: CandidateAction):
    ports = get_ports(get_settings().dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    c, demand = _candidate_bundle(store, candidate_id)
    result = orchestrator.run_final_check_and_reserve(store, c, demand, actor, ports)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.get("/interviews")
def list_interviews(project_id: str | None = None):
    store = get_staffing_store()
    orchestrator.expire_interviews(store)
    return {"interviews": [serialize(i) for i in store.list_interviews(project_id)]}


@router.get("/kb/requests")
def list_kb_requests(project_id: str | None = None):
    store = get_staffing_store()
    return {"requests": [serialize(r) for r in store.list_kb_requests(project_id)]}


@router.get("/hiring-requests/email-defaults")
def mnh_email_defaults():
    settings = get_settings()
    return {"hr_to": settings.mnh_hr_to, "bu_lead_cc": settings.mnh_bu_lead_cc_default}


@router.post("/hiring-requests/preview-email")
def preview_hiring_email(body: HiringRequestCreate):
    """Build the HR email draft (To HR, Cc BU lead). No email is sent yet."""
    settings = get_settings()
    email_draft = build_staffing_email(
        project_id=body.project_id,
        capability=body.capability,
        headcount=body.headcount,
        justification=body.justification,
        start_date=body.start_date,
        end_date=body.end_date,
        position_id=body.position_id,
        filters=body.filters,
        required_skills=body.required_skills,
        pool_outcome=body.pool_outcome,
        bu_lead_cc=body.bu_lead_cc,
        project_lead_name=body.project_lead_name,
        project_lead_email=body.project_lead_email,
    )
    return {
        "email_draft": email_draft,
        "defaults": {
            "hr_to": settings.mnh_hr_to,
            "bu_lead_cc": settings.mnh_bu_lead_cc_default,
        },
    }


@router.post("/hiring-requests")
def create_hiring_request(body: HiringRequestCreate):
    ports = get_ports(get_settings().dev_launch_token)
    actor = _actor(body.launch_token)
    store = get_staffing_store()
    context = body.model_dump(
        exclude={
            "launch_token",
            "project_id",
            "capability",
            "headcount",
            "justification",
        },
        exclude_none=True,
    )
    try:
        return orchestrator.request_hiring(
            store,
            ports,
            body.project_id,
            body.capability,
            body.headcount,
            body.justification,
            actor,
            context=context,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get("/hiring-requests")
def list_hiring_requests(project_id: str | None = None):
    store = get_staffing_store()
    return {"requests": [serialize(h) for h in store.list_hiring_requests(project_id)]}


@router.get("/audit")
def list_audit(limit: int = 100):
    store = get_staffing_store()
    return {"events": store.list_audit(max(1, min(limit, 500)))}


@router.post("/events/project-track")
def project_track_event(body: ProjectTrackEvent):
    settings = get_settings()
    ports = get_ports(settings.dev_launch_token)
    store = get_staffing_store()
    return handle_project_event(store, body.model_dump(), ports)


@router.post("/admin/reconcile")
def admin_reconcile():
    ports = get_ports(get_settings().dev_launch_token)
    return reconcile(get_staffing_store(), ports)


@router.post("/admin/expire-interviews")
def admin_expire_interviews():
    return {"expired": orchestrator.expire_interviews(get_staffing_store())}


@router.post("/admin/outbox/publish")
def admin_publish_outbox(force: bool = True):
    ports = get_ports(get_settings().dev_launch_token)
    return publish_pending(get_staffing_store(), ports, force=force)


@router.get("/admin/pt-writes")
def admin_pt_writes():
    ports = get_ports(get_settings().dev_launch_token)
    return {"rows": ports.written_rows}
