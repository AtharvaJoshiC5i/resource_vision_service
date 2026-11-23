from __future__ import annotations

CANDIDATE_TRANSITIONS: dict[tuple[str, str], str] = {
    ("New", "direct_select"): "Skills Matched",
    ("New", "send_kb"): "KB Pending",
    ("KB Pending", "kb_start"): "Training",
    ("Training", "training_success"): "Skills Matched",
    ("Training", "training_failed"): "Training Failed/Delayed",
    ("Training Failed/Delayed", "release"): "Released",
    ("New", "interview"): "Interview Pending",
    ("Skills Matched", "interview"): "Interview Pending",
    ("Interview Pending", "book"): "Interview Booked",
    ("Interview Booked", "expire"): "Expired",
    ("Interview Booked", "pass"): "Skills Matched",
    ("Interview Booked", "reject"): "Rejected",
    ("Skills Matched", "final_check_ok"): "Reserved",
    ("Reserved", "pt_confirmed"): "Confirmed",
    ("Reserved", "release"): "Released",
    ("Confirmed", "release"): "Released",
    ("Expired", "interview"): "Interview Pending",
    ("Training Failed/Delayed", "send_kb"): "KB Pending",
    ("Training Failed/Delayed", "interview"): "Interview Pending",
}

# Any candidate that has not reached a terminal state can be released by the lead
# or by a Project Track cancellation event.
for _state in (
    "New",
    "Skills Matched",
    "KB Pending",
    "Training",
    "Interview Pending",
    "Interview Booked",
    "Expired",
    "Rejected",
):
    CANDIDATE_TRANSITIONS[(_state, "release")] = "Released"

TERMINAL_STATES = frozenset({"Released", "Rejected", "Expired"})

AVAILABILITY_AFFECTING = frozenset({"Reserved", "Confirmed"})


def transition(current: str, event: str) -> str:
    key = (current, event)
    if key not in CANDIDATE_TRANSITIONS:
        raise ValueError(f"Invalid transition from {current!r} on event {event!r}")
    return CANDIDATE_TRANSITIONS[key]


def can_transition(current: str, event: str) -> bool:
    return (current, event) in CANDIDATE_TRANSITIONS


def affects_availability(status: str) -> bool:
    return status in AVAILABILITY_AFFECTING