from datetime import datetime
import json
from pathlib import Path

import pytest

from helpdesk.bootstrap.context import DemoClock
from helpdesk.domain.contracts import ActionRequest
from helpdesk.domain.lifecycle import transition
from helpdesk.policy.approvals import ApprovalService
from helpdesk.policy.engine import PolicyEngine
from helpdesk.storage.repository import AccessDenied, Repository
from helpdesk.tools.read_tools import ReadTools

ROOT = Path(__file__).resolve().parents[2]


def setup(seeded_db, tmp_path, scenario="production_access", employee="EMP-001"):
    path, config = seeded_db(scenario)
    repo = Repository(path)
    clock = DemoClock(datetime.fromisoformat(config["clock"]))
    session = repo.create_demo_session(employee)
    case = repo.create_case(session, clock)
    context = repo.context(session, case.case_id, clock)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text((ROOT / "data/policies/action_rules.json").read_text(encoding="utf-8"), encoding="utf-8")
    engine = PolicyEngine(repo, policy_path)
    service = ApprovalService(engine)
    tools = ReadTools(repo, ROOT / "data/knowledge")
    return repo, context, engine, service, tools


def action(context, tools, operation="grant_demo_access", resource="snowflake-prod", environment="PROD", role="reader"):
    article = {"snowflake-prod": "KB-008", "grafana-internal": "KB-009", "okta": "KB-001", "vpn": "KB-005"}[resource]
    evidence = tools.call(context, "get_runbook", {"article_id": article}).evidence_ids
    if operation == "grant_demo_access":
        evidence += tools.call(context, "get_employee_context", {}).evidence_ids
        parameters = {"role": role, "business_justification": "Read production metrics for team reporting"}
    else:
        evidence += tools.call(context, "get_diagnostic_snapshot", {"service_id": resource}).evidence_ids
        parameters = {"device_id": tools.call(context, "get_employee_context", {}).data["devices"][0]["device_id"]} if resource == "vpn" else {}
    return ActionRequest(operation=operation, resource_id=resource, environment=environment, parameters=parameters, evidence_ids=evidence)


def consent(repo, context, operation):
    case = repo.get_case(context)
    repo.save_case(context, transition(case, case.status, context.clock.now(), facts={**case.facts, "consent_operations": [operation]}))


def test_prod_access_requires_current_manager_approval_and_persists_on_restart(seeded_db, tmp_path):
    repo, ctx, engine, service, tools = setup(seeded_db, tmp_path)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    assert proposal.decision.decision == "approval_required" and approval.status == "pending"
    assert not service.is_authorized(ctx, proposal.proposal_id)
    assert repo.source("access_grants", "GRANT-001")["employee_id"] == "EMP-004"
    manager = repo.create_demo_session("EMP-005")
    assert [a.approval_id for a in service.pending(manager, ctx.clock)] == [approval.approval_id]
    decided = service.decide(manager, approval.approval_id, True, ctx.clock)
    assert decided.decided_by == "EMP-005"
    restarted = ApprovalService(PolicyEngine(Repository(repo.path), engine.path))
    assert restarted.is_authorized(ctx, proposal.proposal_id)
    assert len(repo.sources("access_grants")) == 1  # Approval has no side effect.


def test_requester_other_manager_and_cross_case_cannot_use_approval(seeded_db, tmp_path):
    repo, ctx, _, service, tools = setup(seeded_db, tmp_path)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    for session in [ctx.session_id, repo.create_demo_session("EMP-006")]:
        with pytest.raises(AccessDenied):
            service.decide(session, approval.approval_id, True, ctx.clock)
    other = repo.create_demo_session("EMP-004")
    other_case = repo.create_case(other, ctx.clock)
    assert not service.is_authorized(repo.context(other, other_case.case_id, ctx.clock), proposal.proposal_id)


def test_rejection_and_expiry_never_authorize(seeded_db, tmp_path):
    repo, ctx, _, service, tools = setup(seeded_db, tmp_path)
    manager = repo.create_demo_session("EMP-005")
    proposal, approval = service.propose(ctx, action(ctx, tools))
    assert service.decide(manager, approval.approval_id, False, ctx.clock).status == "rejected"
    assert not service.is_authorized(ctx, proposal.proposal_id)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    ctx.clock.advance(1800)
    assert service.decide(manager, approval.approval_id, True, ctx.clock).status == "expired"
    assert not service.is_authorized(ctx, proposal.proposal_id)


def test_approved_scope_cannot_be_reused_after_policy_version_change(seeded_db, tmp_path):
    repo, ctx, engine, service, tools = setup(seeded_db, tmp_path)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    manager = repo.create_demo_session("EMP-005")
    service.decide(manager, approval.approval_id, True, ctx.clock)
    policy = json.loads(engine.path.read_text(encoding="utf-8"))
    policy["version"] = "2.0"
    engine.path.write_text(json.dumps(policy), encoding="utf-8")
    assert not service.is_authorized(ctx, proposal.proposal_id)


def test_scope_tampering_and_double_decision_are_rejected(seeded_db, tmp_path):
    repo, ctx, _, service, tools = setup(seeded_db, tmp_path)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    manager = repo.create_demo_session("EMP-005")
    with repo.transaction() as db:
        payload = proposal.model_dump(mode="json")
        payload["action"]["parameters"]["role"] = "writer"
        db.execute("UPDATE proposals SET payload=? WHERE record_id=?", (json.dumps(payload), proposal.proposal_id))
    with pytest.raises(ValueError, match="scope"):
        service.decide(manager, approval.approval_id, True, ctx.clock)
    assert not service.is_authorized(ctx, proposal.proposal_id)
    _, approval2 = service.propose(ctx, action(ctx, tools))
    service.decide(manager, approval2.approval_id, True, ctx.clock)
    with pytest.raises(ValueError, match="already decided"):
        service.decide(manager, approval2.approval_id, True, ctx.clock)


def test_deny_precedence_unknown_rule_and_forged_parameters(seeded_db, tmp_path):
    _, ctx, engine, _, tools = setup(seeded_db, tmp_path)
    policy = json.loads(engine.path.read_text(encoding="utf-8"))
    allow = {**policy["rules"][2], "rule_id": "OVERLAP-ALLOW", "decision": "allow", "approver_role": None}
    deny = {**allow, "rule_id": "OVERLAP-DENY", "decision": "deny"}
    policy["rules"] += [allow, deny]
    engine.path.write_text(json.dumps(policy), encoding="utf-8")
    decision = engine.evaluate(ctx, action(ctx, tools))
    assert decision.decision == "deny" and decision.rule_ids == ["OVERLAP-DENY"]
    assert engine.evaluate(ctx, ActionRequest(operation="delete_account", resource_id="okta", environment="INTERNAL")).decision == "deny"
    request = action(ctx, tools)
    forged = ActionRequest(**{**request.model_dump(), "parameters": {**request.parameters, "employee_id": "EMP-005", "identity_verified": True}})
    assert engine.evaluate(ctx, forged).decision == "deny"


def test_grafana_grant_requires_consent_and_remains_independent_of_prod(seeded_db, tmp_path):
    repo, ctx, engine, service, tools = setup(seeded_db, tmp_path)
    request = action(ctx, tools, resource="grafana-internal", environment="INTERNAL", role="viewer")
    assert engine.evaluate(ctx, request).decision == "deny"
    consent(repo, ctx, "grant_demo_access")
    assert engine.evaluate(ctx, request).decision == "allow"
    assert service.propose(ctx, request)[1] is None
    assert engine.evaluate(ctx, action(ctx, tools)).decision == "approval_required"


def test_missing_evidence_or_policy_fails_closed(seeded_db, tmp_path):
    _, ctx, engine, _, tools = setup(seeded_db, tmp_path)
    request = action(ctx, tools)
    for ids in [[], ["fabricated-evidence"]]:
        invalid = ActionRequest(**{**request.model_dump(), "evidence_ids": ids})
        assert engine.evaluate(ctx, invalid).decision == "deny"
    engine.path.write_text('{"broken": true}', encoding="utf-8")
    assert engine.evaluate(ctx, request).decision == "deny"


def test_incomplete_policy_and_revoked_manager_role_fail_closed(seeded_db, tmp_path):
    repo, ctx, engine, service, tools = setup(seeded_db, tmp_path)
    proposal, approval = service.propose(ctx, action(ctx, tools))
    manager = repo.create_demo_session("EMP-005")
    service.decide(manager, approval.approval_id, True, ctx.clock)
    with repo.transaction() as db:
        row = json.loads(db.execute("SELECT payload FROM employees WHERE record_id='EMP-005'").fetchone()[0])
        row["roles"] = ["employee"]
        db.execute("UPDATE employees SET payload=? WHERE record_id='EMP-005'", (json.dumps(row),))
    assert not service.is_authorized(ctx, proposal.proposal_id)
    policy = json.loads(engine.path.read_text(encoding="utf-8"))
    del policy["version"]
    engine.path.write_text(json.dumps(policy), encoding="utf-8")
    assert engine.evaluate(ctx, proposal.action).decision == "deny"


@pytest.mark.parametrize("scenario,allowed", [("vpn_stale_profile", True), ("vpn_regional_outage", False), ("conflicting_evidence", False)])
def test_profile_refresh_cannot_bypass_outage_or_stale_status(seeded_db, tmp_path, scenario, allowed):
    repo, ctx, engine, _, tools = setup(seeded_db, tmp_path, scenario, "EMP-004")
    consent(repo, ctx, "refresh_demo_vpn_profile")
    request = action(ctx, tools, "refresh_demo_vpn_profile", "vpn", "INTERNAL")
    assert (engine.evaluate(ctx, request).decision == "allow") == allowed


def test_unlock_requires_observed_lock_consent_and_self_scope(seeded_db, tmp_path):
    repo, ctx, engine, _, tools = setup(seeded_db, tmp_path, "account_lockout", "EMP-003")
    request = action(ctx, tools, "unlock_demo_account", "okta", "INTERNAL")
    assert engine.evaluate(ctx, request).decision == "deny"
    consent(repo, ctx, "unlock_demo_account")
    assert engine.evaluate(ctx, request).decision == "allow"
    foreign = ActionRequest(**{**request.model_dump(), "parameters": {"employee_id": "EMP-001"}})
    assert engine.evaluate(ctx, foreign).decision == "deny"
