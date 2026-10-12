from helpdesk.evaluation.scoring import score_case


def test_claimed_resolution_without_verification_is_a_failure():
    result = score_case("baseline", {"status": "resolved", "verification": None, "tool_errors": []}, [], [], None)
    assert not result["passed"] and not result["checks"]["resolved_has_verification"]


def test_escalation_without_context_is_not_success():
    result = score_case("pipeline_maintenance", {"status": "escalated", "tool_errors": []}, [], [], None)
    assert not result["passed"] and not result["checks"]["escalated_has_context"]
