from test_policy_approvals import setup

import pytest

from helpdesk.escalation.service import HandoffService
from helpdesk.domain.lifecycle import transition
from helpdesk.storage.repository import AccessDenied, Repository


def test_handoff_preserves_context_and_creation_is_not_acknowledgement(seeded_db, tmp_path):
    repo, ctx, _, _, tools = setup(seeded_db, tmp_path, "pipeline_maintenance", "EMP-004")
    repo.append_message(ctx, "employee", "Since Friday maintenance, Jenkins times out and Tableau is stale.")
    tools.call(ctx, "get_diagnostic_snapshot", {"service_id": "jenkins"})
    tools.call(ctx, "get_recent_changes", {"service_ids": ["jenkins"], "since": "2026-10-09T00:00:00+08:00"})
    case = repo.get_case(ctx)
    repo.save_case(ctx, transition(case, case.status, ctx.clock.now(), missing_information=["Whether all jobs are affected"], tool_errors=[{"code": "TIMEOUT"}], attempted_fixes=[{"operation": "guided_check", "outcome": "failed"}]))
    service = HandoffService(repo)
    result = service.create(ctx, "Production repair requires SRE")
    assert result["status"] == "queued"
    reviewer = repo.create_demo_session("EMP-007")
    package = service.queue(reviewer)[0]
    assert package["support_group"] == "sre"
    assert package["evidence"] and package["attempted_fixes"] and package["tool_errors"]
    assert package["unresolved_questions"] == ["Whether all jobs are affected"]
    assert package["acknowledged_by"] is None
    assert service.create(ctx, "duplicate")["handoff_id"] == result["handoff_id"]
    reopened = HandoffService(Repository(repo.path))
    assert reopened.acknowledge(reviewer, result["handoff_id"], ctx.clock)["acknowledged_by"] == "EMP-007"
    assert repo.get_case(ctx).status == "escalated"


def test_employee_cannot_read_queue_and_specialists_are_group_scoped(seeded_db, tmp_path):
    repo, ctx, _, _, _ = setup(seeded_db, tmp_path)
    repo.append_message(ctx, "employee", "I suspect an account compromise")
    service = HandoffService(repo)
    result = service.create(ctx, "Potential breach")
    with pytest.raises(AccessDenied):
        service.queue(ctx.session_id)
    it = repo.create_demo_session("EMP-007")
    assert service.queue(it) == []
    with pytest.raises(AccessDenied):
        service.acknowledge(it, result["handoff_id"], ctx.clock)
    security = repo.create_demo_session("EMP-008")
    assert service.acknowledge(security, result["handoff_id"], ctx.clock)["status"] == "acknowledged"
