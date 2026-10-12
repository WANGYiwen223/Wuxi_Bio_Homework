"""Case transitions preserve verification and escalation invariants."""

from datetime import datetime
from typing import Any

from helpdesk.domain.contracts import Case, CaseStatus

TRANSITIONS = {
    "investigating": {"awaiting_employee", "awaiting_approval", "awaiting_verification", "escalated"},
    "awaiting_employee": {"investigating", "awaiting_verification", "resolved", "escalated"},
    "awaiting_approval": {"investigating", "awaiting_verification", "escalated"},
    "awaiting_verification": {"awaiting_employee", "investigating", "resolved", "escalated"},
    "resolved": set(),
    "escalated": set(),
}


def transition(case: Case, status: CaseStatus, now: datetime, **updates: Any) -> Case:
    if status != case.status and status not in TRANSITIONS[case.status]:
        raise ValueError(f"Invalid case transition: {case.status} -> {status}")
    if {"case_id", "employee_id", "session_id", "created_at", "version", "status", "updated_at"} & updates.keys():
        raise ValueError("Case identity/lifecycle fields cannot be supplied as updates")
    return Case.model_validate({**case.model_dump(), **updates, "status": status, "updated_at": now})
