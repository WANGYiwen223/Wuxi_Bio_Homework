"""The same fault is reusable; identity, authorization and effects stay scoped."""

import json

import pytest

from helpdesk.resolution.service import ResolutionService
from test_policy_approvals import setup, action, consent


def context_for(repo, employee_id, clock):
    session = repo.create_demo_session(employee_id)
    case = repo.create_case(session, clock)
    return repo.context(session, case.case_id, clock)


@pytest.mark.parametrize("employee", ["EMP-001", "EMP-002", "EMP-004"])
def test_same_employee_has_two_independent_problems_and_repairs_are_personal(seeded_db, tmp_path, employee):
    # All selected employees receive both conditions in this small mixed world.
    def mixed(_):
        return seeded_db("mixed_issues", ["EMP-001", "EMP-002", "EMP-004"])

    repo, ctx, _, approvals, reads = setup(mixed, tmp_path, "mixed_issues", employee)
    before_accounts = repo.sources("account_states")
    before_devices = repo.sources("devices")
    service = ResolutionService(approvals)
    consent(repo, ctx, "unlock_demo_account")
    proposal, _ = approvals.propose(ctx, action(ctx, reads, "unlock_demo_account", "okta", "INTERNAL"))
    assert service.execute(ctx, proposal.proposal_id)["status"] == "success"
    assert service.verify(ctx, proposal.proposal_id, True).outcome == "success"
    assert repo.sources("devices") == before_devices  # Unlock did not fix VPN.

    vpn_ctx = context_for(repo, employee, ctx.clock)
    consent(repo, vpn_ctx, "refresh_demo_vpn_profile")
    proposal, _ = approvals.propose(vpn_ctx, action(vpn_ctx, reads, "refresh_demo_vpn_profile", "vpn", "INTERNAL"))
    assert service.execute(vpn_ctx, proposal.proposal_id)["status"] == "success"
    assert service.verify(vpn_ctx, proposal.proposal_id, True).outcome == "success"
    assert [a for a in repo.sources("account_states") if a["employee_id"] != employee] == [a for a in before_accounts if a["employee_id"] != employee]
    assert [d for d in repo.sources("devices") if d["employee_id"] != employee] == [d for d in before_devices if d["employee_id"] != employee]


def test_shared_incident_is_read_by_multiple_authorized_people_with_separate_evidence(seeded_db, tmp_path):
    repo, ctx, _, _, reads = setup(seeded_db, tmp_path, "pipeline_maintenance", "EMP-001")
    for service, resource, snapshot in [("jenkins", "jenkins-sales-etl", "BUILD-001"), ("tableau", "tableau-sales-dashboard", "REPORT-001")]:
        results = []
        for employee in ["EMP-001", "EMP-004", "EMP-007"]:
            actor = context_for(repo, employee, ctx.clock)
            result = reads.call(actor, "get_diagnostic_snapshot", {"service_id": service, "resource_id": resource})
            assert result.status == "success"
            assert result.data[0]["snapshot_id"] == snapshot
            assert result.data[0]["employee_id"] is None
            assert all(e.employee_id == employee for e in repo.evidence(actor))
            results.append(result)
        assert results[0].data == results[1].data == results[2].data
        assert results[0].evidence_ids != results[1].evidence_ids


def test_shared_resource_scope_cannot_be_bypassed_and_revocation_is_immediate(seeded_db, tmp_path):
    repo, ctx, _, _, reads = setup(seeded_db, tmp_path, "pipeline_maintenance", "EMP-002")
    assert reads.call(ctx, "get_employee_context", {}).data["diagnostic_resources"] == []
    assert reads.call(ctx, "get_diagnostic_snapshot", {"service_id": "jenkins"}).status == "not_found"
    denied = reads.call(ctx, "get_diagnostic_snapshot", {"service_id": "jenkins", "resource_id": "jenkins-sales-etl"})
    assert denied.status == "denied" and not denied.evidence_ids
    reviewer = context_for(repo, "EMP-007", ctx.clock)
    assert reads.call(reviewer, "get_diagnostic_snapshot", {"service_id": "jenkins"}).status == "success"
    with repo.transaction() as db:
        row = json.loads(db.execute("SELECT payload FROM employees WHERE record_id='EMP-007'").fetchone()[0])
        row["roles"] = ["employee"]
        db.execute("UPDATE employees SET payload=? WHERE record_id='EMP-007'", (json.dumps(row),))
    assert reads.call(reviewer, "get_diagnostic_snapshot", {"service_id": "jenkins", "resource_id": "jenkins-sales-etl"}).status == "denied"
    assert reads.call(ctx, "get_diagnostic_snapshot", {"service_id": "jenkins", "device_id": "DEV-002", "resource_id": "jenkins-sales-etl"}).error.code == "INVALID_ARGUMENTS"


@pytest.mark.parametrize("employee,expected", [("EMP-001", "approval_required"), ("EMP-004", "approval_required"), ("EMP-002", "deny")])
def test_access_requests_depend_on_department_and_actual_manager(seeded_db, tmp_path, employee, expected):
    repo, ctx, _, approvals, reads = setup(seeded_db, tmp_path, "production_access", employee)
    proposal, approval = approvals.propose(ctx, action(ctx, reads))
    assert proposal.decision.decision == expected
    if approval:
        assert approval.approver_id == repo.source("employees", employee)["manager_id"]
        assert approval.employee_id == employee
    else:
        assert expected == "deny"


@pytest.mark.parametrize("employee,affected", [("EMP-001", False), ("EMP-002", True), ("EMP-004", True)])
def test_same_regional_incident_has_location_specific_action_and_verification(seeded_db, tmp_path, employee, affected):
    repo, ctx, _, approvals, reads = setup(seeded_db, tmp_path, "vpn_regional_outage", employee)
    consent(repo, ctx, "refresh_demo_vpn_profile")
    proposal, _ = approvals.propose(ctx, action(ctx, reads, "refresh_demo_vpn_profile", "vpn", "INTERNAL"))
    assert proposal.decision.decision == ("deny" if affected else "allow")
    if not affected:
        service = ResolutionService(approvals)
        assert service.execute(ctx, proposal.proposal_id)["status"] == "success"
        verification = service.verify(ctx, proposal.proposal_id, True)
        assert verification.outcome == "success"
        assert verification.observations["service_status_applies"] is False
