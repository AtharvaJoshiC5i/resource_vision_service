from __future__ import annotations

from pydantic import BaseModel, Field


class LaunchFilters(BaseModel):
    primary_capability: list[str] = Field(default_factory=list)
    secondary_capability: list[str] = Field(default_factory=list)
    department: list[str] = Field(default_factory=list)
    location: list[str] = Field(default_factory=list)
    country: list[str] = Field(default_factory=list)
    grade: list[str] = Field(default_factory=list)


class RequiredSkill(BaseModel):
    name: str
    level: str


class MonthHours(BaseModel):
    month_key: str
    hours: float


class PoolSearchRequest(BaseModel):
    project_id: str
    start_date: str
    end_date: str
    filters: LaunchFilters | None = None
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    month_hours: list[MonthHours] = Field(default_factory=list)
    search: str | None = None
    availability_filter: str | None = "all"
    skill_match_filter: str | None = "all"
    allow_mnh: bool = False
    launch_token: str | None = None


class DemandCreate(BaseModel):
    project_id: str
    proposal_number: str | None = None
    sub_project_name: str | None = None
    position_id: str | None = None
    start_date: str
    end_date: str
    filters: dict = Field(default_factory=dict)
    required_skills: list[dict] = Field(default_factory=list)
    launch_token: str
    project_status: str | None = "confirmed"


class CandidateCreate(BaseModel):
    launch_token: str
    demand_id: str
    employee_key: str


class CandidateHours(BaseModel):
    months: list[MonthHours]


class CandidateAction(BaseModel):
    launch_token: str


class KbBatchAction(BaseModel):
    launch_token: str
    candidate_ids: list[str]


class InterviewOutcome(BaseModel):
    launch_token: str
    outcome: str  # pass | reject
    rejection_type: str | None = None  # Technical | Non-technical
    reason: str | None = None


class TrainingOutcome(BaseModel):
    launch_token: str
    outcome: str  # success | failed
    reason: str | None = None


class HiringRequestCreate(BaseModel):
    launch_token: str
    project_id: str
    capability: str
    headcount: int = 1
    justification: str = "Internal staffing shortage"
    start_date: str | None = None
    end_date: str | None = None
    position_id: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    required_skills: list[dict[str, str]] = Field(default_factory=list)
    month_hours: list[dict[str, object]] = Field(default_factory=list)
    pool_outcome: dict[str, object] | None = None
    source: str | None = None
    bu_lead_cc: str | None = None
    project_lead_name: str | None = None
    project_lead_email: str | None = None


class LaunchValidate(BaseModel):
    launch_token: str


class ProjectTrackEvent(BaseModel):
    type: str
    project_id: str
    payload: dict = Field(default_factory=dict)