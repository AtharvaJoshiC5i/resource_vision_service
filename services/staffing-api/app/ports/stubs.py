from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

logger = logging.getLogger("staffing.ports")


class IdentityPort(Protocol):
    def resolve(self, launch_token: str) -> dict[str, Any]: ...


class SkillsProviderPort(Protocol):
    def get_skills(self, employee_codes: list[str]) -> list[dict]: ...
    def get_options(self) -> dict: ...
    def refresh(self) -> None: ...


class ProjectTrackReadPort(Protocol):
    def fresh_snapshot_rows(self) -> tuple[list[dict], list[dict]]: ...


class ProjectTrackWriterPort(Protocol):
    def write_allocation(self, payload: dict, idempotency_key: str) -> dict: ...


class ProjectTrackEventsPort(Protocol):
    def publish(self, event: dict) -> None: ...


class KBTrainingPort(Protocol):
    def send_training_request(self, payload: dict) -> dict: ...


class MNHPort(Protocol):
    def request_hire(self, payload: dict) -> dict: ...


class NotificationsPort(Protocol):
    def notify(self, channel: str, message: str, meta: dict | None = None) -> None: ...


class ZingHRStatusPort(Protocol):
    def emit_intent(self, employee_key: str, status: str) -> None: ...


@dataclass
class StubPorts:
    identity: IdentityPort
    skills: SkillsProviderPort
    pt_read: ProjectTrackReadPort
    pt_write: ProjectTrackWriterPort
    pt_events: ProjectTrackEventsPort
    kb: KBTrainingPort
    mnh: MNHPort
    notifications: NotificationsPort
    zinghr_status: ZingHRStatusPort
    kb_force_success: bool = True
    kb_force_failure: bool = False
    written_rows: list[dict] = field(default_factory=list)
    event_log: list[dict] = field(default_factory=list)


class StubIdentity:
    def __init__(self, dev_token: str):
        self.dev_token = dev_token

    def resolve(self, launch_token: str) -> dict[str, Any]:
        if launch_token != self.dev_token:
            raise PermissionError("Invalid launch token")
        return {"user_id": "simulator-user", "display_name": "Simulator Lead"}


class StubSkills:
    """Synthetic skills for demo mode: stable per employee code, includes one level outside the
    configured order and one undocumented level so those display paths are exercised."""

    _names = ["Python", "SQL", "Spark", "Azure", "Power BI", "React", "Machine Learning", "Data Modeling"]
    _levels = ["Foundational", "Applied", "Advanced", "Expert", "Practitioner"]

    def get_skills(self, employee_codes: list[str]) -> list[dict]:
        out = []
        for code in employee_codes:
            seed = sum(ord(c) * (i + 1) for i, c in enumerate(code.upper()))
            for k in range(2 + seed % 4):
                name = self._names[(seed + k * 3) % len(self._names)]
                level = None if (seed + k) % 11 == 0 else self._levels[(seed // (k + 1) + k) % len(self._levels)]
                out.append({"employee_code": code, "skill_name": name, "current_level": level})
        return out

    def get_options(self) -> dict:
        return {"skills": sorted(self._names), "levels": list(self._levels), "available": True}

    def refresh(self) -> None:
        pass


class StubPTRead:
    def fresh_snapshot_rows(self) -> tuple[list[dict], list[dict]]:
        return [], []


class StubPTWriter:
    def __init__(self, store: list[dict]):
        self.store = store
        self._lock = threading.Lock()

    def write_allocation(self, payload: dict, idempotency_key: str) -> dict:
        with self._lock:
            for row in self.store:
                if row.get("idempotency_key") == idempotency_key:
                    return {"status": "duplicate", "idempotency_key": idempotency_key}
            payload = {**payload, "idempotency_key": idempotency_key, "written_at": datetime.utcnow().isoformat()}
            self.store.append(payload)
            return {"status": "confirmed", "idempotency_key": idempotency_key}


class StubPTEvents:
    def __init__(self, log: list[dict]):
        self.log = log

    def publish(self, event: dict) -> None:
        self.log.append({**event, "at": datetime.utcnow().isoformat()})


class StubKB:
    def __init__(self, ports: StubPorts):
        self.ports = ports

    def send_training_request(self, payload: dict) -> dict:
        if self.ports.kb_force_failure:
            return {"accepted": False, "reason": "stub failure"}
        logger.info(
            "KB SKILL_GAP_TRAINING request_id=%s employees=%s",
            payload.get("request_id"),
            payload.get("selected_employee_count"),
        )
        return {"accepted": True, "training_id": "stub-tr-1", "payload": payload}

    def send_interview_rejection_feedback(self, payload: dict) -> dict:
        """Technical interview rejections only; surfaced on the KB tab via interview rows."""
        return {"accepted": True, "feedback_id": "stub-kb-fb-1", "payload": payload}


class StubMNH:
    def request_hire(self, payload: dict) -> dict:
        import uuid

        return {
            "status": "Hiring in progress",
            "request_id": f"stub-mnh-{uuid.uuid4().hex[:12]}",
            "mock_email_sent": True,
            "payload": payload,
        }


class StubNotifications:
    def notify(self, channel: str, message: str, meta: dict | None = None) -> None:
        logger.info("notify %s: %s %s", channel, message, meta or {})


class StubZingHRStatus:
    def emit_intent(self, employee_key: str, status: str) -> None:
        logger.info("zinghr intent %s -> %s", employee_key, status)


_ports: StubPorts | None = None
_ports_mode: str | None = None


def reset_ports_cache() -> None:
    global _ports, _ports_mode
    _ports = None
    _ports_mode = None


def get_ports(dev_token: str = "dev-simulator-token") -> StubPorts:
    global _ports, _ports_mode
    from app.config import get_settings

    mode = get_settings().resolved_rv_data_source()
    if _ports is not None and _ports_mode != mode:
        reset_ports_cache()
    if _ports is None:
        from app.ports.azure_data import AzureProjectTrackRead, AzureSkillsProvider

        written: list[dict] = []
        events: list[dict] = []
        pt_write = StubPTWriter(written)
        use_azure_sources = get_settings().resolved_rv_data_source() != "demo"
        skills: SkillsProviderPort = AzureSkillsProvider() if use_azure_sources else StubSkills()
        pt_read: ProjectTrackReadPort = AzureProjectTrackRead() if use_azure_sources else StubPTRead()
        _ports = StubPorts(
            identity=StubIdentity(dev_token),
            skills=skills,
            pt_read=pt_read,
            pt_write=pt_write,
            pt_events=StubPTEvents(events),
            kb=StubKB(None),
            mnh=StubMNH(),
            notifications=StubNotifications(),
            zinghr_status=StubZingHRStatus(),
            written_rows=written,
            event_log=events,
        )
        _ports.kb = StubKB(_ports)
        _ports_mode = mode
    return _ports


class AzureProjectTrackWriter(StubPTWriter):
    """Phase 5: replace with SQL insert or PT REST API."""

    pass