import json

import pytest

from test_policy_approvals import setup, action, consent
from helpdesk.domain.contracts import ActionRequest
from helpdesk.resolution.service import ResolutionService


def test_unlock_replays_once_and_needs_employee_confirmation(seeded_db, tmp_path):
    repo, ctx, _, approvals, tools = setup(seeded_db, tmp_path, "account_lockout", "EMP-003")
    consent(repo, ctx, "unlock_demo_account")
    request = action(ctx, tools, "unlock_demo_account", "okta", "INTERNAL")
    service = ResolutionService(approvals)
    proposal, _ = approvals.propose(ctx, request, "retry-safe-call")
    again, _ = approvals.propose(ctx, request, "retry-safe-call")
    assert proposal.proposal_id == again.proposal_id
    first = service.execute(ctx, proposal.proposal_id)
    assert service.execute(ctx, proposal.proposal_id) == first
    assert repo.source("account_states", "OKTA-003")["status"] == "active"
    assert service.verify(ctx, proposal.proposal_id).employee_confirmed is False
    assert repo.get_case(ctx).status == "awaiting_verification"
    assert service.verify(ctx, proposal.proposal_id, True).outcome == "success"
    assert repo.get_case(ctx).status == "resolved"


def test_negative_feedback_returns_to_diagnosis_with_attempt_preserved(seeded_db, tmp_path):
    repo, ctx, _, approvals, tools = setup(seeded_db, tmp_path, "account_lockout", "EMP-003")
    consent(repo, ctx, "unlock_demo_account")
    proposal, _ = approvals.propose(ctx, action(ctx, tools, "unlock_demo_account", "okta", "INTERNAL"))
    service = ResolutionService(approvals)
    service.execute(ctx, proposal.proposal_id)
    assert service.verify(ctx, proposal.proposal_id, False).outcome == "failure"
    assert repo.get_case(ctx).status == "investigating"
    assert repo.get_case(ctx).attempted_fixes[0]["verification"]["outcome"] == "failure"


def test_prod_grant_requires_approval_and_is_idempotent_across_proposals(seeded_db, tmp_path):
    repo, ctx, _, approvals, tools = setup(seeded_db, tmp_path)
    proposal, approval = approvals.propose(ctx, action(ctx, tools))
    service = ResolutionService(approvals)
    assert service.execute(ctx, proposal.proposal_id)["status"] == "denied"
    manager = repo.create_demo_session("EMP-005")
    approvals.decide(manager, approval.approval_id, True, ctx.clock)
    first = service.execute(ctx, proposal.proposal_id)
    assert service.execute(ctx, proposal.proposal_id)["action_id"] == first["action_id"]
    assert len([g for g in repo.sources("access_grants") if g["employee_id"] == "EMP-001"]) == 1
    assert service.verify(ctx, proposal.proposal_id, True).observations["resource_probe_passed"]


def test_policy_change_after_approval_prevents_execution(seeded_db, tmp_path):
    repo, ctx, engine, approvals, tools = setup(seeded_db, tmp_path)
    proposal, approval = approvals.propose(ctx, action(ctx, tools))
    approvals.decide(repo.create_demo_session("EMP-005"), approval.approval_id, True, ctx.clock)
    policy = json.loads(engine.path.read_text())
    policy["version"] = "new"
    engine.path.write_text(json.dumps(policy))
    assert ResolutionService(approvals).execute(ctx, proposal.proposal_id)["status"] == "denied"
    assert len(repo.sources("access_grants")) == 1


def test_vpn_refresh_cannot_fix_outage_and_verifier_observes_new_incident(seeded_db, tmp_path):
    repo, ctx, _, approvals, tools = setup(seeded_db, tmp_path, "vpn_stale_profile", "EMP-004")
    consent(repo, ctx, "refresh_demo_vpn_profile")
    proposal, _ = approvals.propose(ctx, action(ctx, tools, "refresh_demo_vpn_profile", "vpn", "INTERNAL"))
    service = ResolutionService(approvals)
    service.execute(ctx, proposal.proposal_id)
    with repo.transaction() as db:
        row = json.loads(db.execute("SELECT payload FROM services WHERE record_id='vpn'").fetchone()[0])
        row["health"] = "outage"
        db.execute("UPDATE services SET payload=? WHERE record_id='vpn'", (json.dumps(row),))
    assert service.verify(ctx, proposal.proposal_id, True).outcome == "failure"
    assert repo.get_case(ctx).status == "investigating"


def test_replayed_call_with_changed_scope_is_rejected(seeded_db, tmp_path):
    _, ctx, _, approvals, tools = setup(seeded_db, tmp_path)
    request = action(ctx, tools)
    approvals.propose(ctx, request, "fixed-call")
    changed = ActionRequest(**{**request.model_dump(), "parameters": {"role": "writer", "business_justification": "changed"}})
    with pytest.raises(ValueError, match="different action scope"):
        approvals.propose(ctx, changed, "fixed-call")
