from datetime import datetime

import pytest
from pydantic import ValidationError

from helpdesk.domain.contracts import Case, ToolError, ToolResult, VerificationResult
from helpdesk.domain.lifecycle import transition

NOW = datetime.fromisoformat("2026-10-12T10:00:00+08:00")


def case():
    return Case(session_id="s", employee_id="e", created_at=NOW, updated_at=NOW)


def test_tool_errors_cannot_masquerade_as_success_or_healthy_data():
    with pytest.raises(ValidationError):
        ToolResult(tool_call_id="t", status="success", retrieved_at=NOW, error=ToolError(code="TIMEOUT", message="Unavailable"))
    with pytest.raises(ValidationError):
        ToolResult(tool_call_id="t", status="error", retrieved_at=NOW, data={"health": "healthy"})
    with pytest.raises(ValidationError):
        ToolResult(tool_call_id="t", status="success", data={}, retrieved_at=NOW.replace(tzinfo=None))


def test_resolution_needs_valid_transition_verification_and_employee_feedback():
    with pytest.raises(ValueError, match="transition"):
        transition(case(), "resolved", NOW)
    pending = transition(case(), "awaiting_verification", NOW)
    with pytest.raises(ValidationError, match="successful verification"):
        transition(pending, "resolved", NOW)
    v = VerificationResult(outcome="success", method="account_probe", employee_confirmation_required=True)
    with pytest.raises(ValidationError, match="employee confirmation"):
        transition(pending, "resolved", NOW, verification=v)
    confirmed = VerificationResult(**{**v.model_dump(), "employee_confirmed": True})
    assert transition(pending, "resolved", NOW, verification=confirmed).status == "resolved"


def test_identity_and_undurable_escalation_are_rejected():
    with pytest.raises(ValueError, match="identity"):
        transition(case(), "awaiting_employee", NOW, employee_id="other")
    with pytest.raises(ValidationError, match="handoff"):
        transition(case(), "escalated", NOW)
