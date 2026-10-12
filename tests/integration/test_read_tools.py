from datetime import datetime
from pathlib import Path

import pytest

from helpdesk.bootstrap.context import DemoClock
from helpdesk.storage.repository import Repository
from helpdesk.tools.read_tools import ReadTools

KNOWLEDGE = Path(__file__).resolve().parents[2] / "data/knowledge"


def setup(seeded_db, scenario="baseline", employee="EMP-004"):
    path, config = seeded_db(scenario)
    repo = Repository(path)
    clock = DemoClock(datetime.fromisoformat(config["clock"]))
    session = repo.create_demo_session(employee)
    case = repo.create_case(session, clock)
    ctx = repo.context(session, case.case_id, clock)
    return repo, ctx, ReadTools(repo, KNOWLEDGE, config["faults"])


def test_employee_tool_is_session_scoped_and_rejects_identity_arguments(seeded_db):
    repo, ctx, tools = setup(seeded_db)
    result = tools.call(ctx, "get_employee_context", {})
    assert result.data["employee"]["employee_id"] == "EMP-004"
    assert {d["employee_id"] for d in result.data["devices"]} == {"EMP-004"}
    assert result.evidence_ids and repo.evidence(ctx)
    invalid = tools.call(ctx, "get_employee_context", {"employee_id": "EMP-001"})
    assert invalid.error.code == "INVALID_ARGUMENTS"


def test_foreign_diagnostic_target_denied_without_evidence(seeded_db):
    repo, ctx, tools = setup(seeded_db)
    result = tools.call(ctx, "get_diagnostic_snapshot", {"service_id": "vpn", "device_id": "DEV-001"})
    assert result.status == "denied" and not result.evidence_ids
    assert repo.evidence(ctx) == []


def test_vpn_retrieval_exposes_competing_causes(seeded_db):
    _, ctx, tools = setup(seeded_db)
    result = tools.call(ctx, "search_resolution_history", {"query": "VPN disconnects", "service_id": "vpn", "limit": 5})
    assert {r["root_cause"] for r in result.data} == {"Stale VPN profile", "Regional gateway outage"}
    runbooks = tools.call(ctx, "search_knowledge", {"query": "VPN disconnects", "service_id": "vpn", "limit": 5})
    assert {"KB-004", "KB-005", "KB-006"} <= {r["article_id"] for r in runbooks.data}


def test_status_preserves_conflicting_timestamps_and_incident_evidence(seeded_db):
    repo, ctx, tools = setup(seeded_db, "conflicting_evidence")
    result = tools.call(ctx, "get_service_status", {"service_id": "vpn", "region": "us-central"})
    assert result.data["health"] == "healthy"
    assert result.data["incidents"][0]["status"] == "investigating"
    assert result.sources[0].observed_at < result.sources[1].observed_at
    assert len(repo.evidence(ctx)) == 2


def test_missing_service_and_wrong_region_are_unknown_not_healthy(seeded_db):
    _, ctx, tools = setup(seeded_db, "vpn_regional_outage")
    for args in [{"service_id": "missing"}, {"service_id": "vpn", "region": "ap-east"}]:
        result = tools.call(ctx, "get_service_status", args)
        assert result.status == "not_found" and result.data is None


def test_timeout_counter_survives_gateway_restart_and_does_not_change_health(seeded_db):
    repo, ctx, tools = setup(seeded_db, "tool_timeout")
    first = tools.call(ctx, "get_service_status", {"service_id": "vpn"})
    assert first.status == "error" and first.error.retryable and first.data is None
    restarted = ReadTools(Repository(repo.path), KNOWLEDGE, tools.faults)
    assert restarted.call(ctx, "get_service_status", {"service_id": "vpn"}).error.code == "TOOL_TIMEOUT"
    assert restarted.call(ctx, "get_service_status", {"service_id": "vpn"}).data["health"] == "healthy"


def test_changes_and_runbook_read_have_source_ids_and_time_filters(seeded_db):
    _, ctx, tools = setup(seeded_db)
    result = tools.call(ctx, "get_recent_changes", {"service_ids": ["jenkins"], "since": "2026-10-09T00:00:00+08:00", "environment": "PROD"})
    assert result.data[0]["change_id"] == "CHG-001"
    assert result.sources[0].source_id == "change:CHG-001"
    missing = tools.call(ctx, "get_recent_changes", {"service_ids": ["jenkins"], "since": "2026-10-10T00:00:00+08:00"})
    assert missing.status == "not_found"
    runbook = tools.call(ctx, "get_runbook", {"article_id": "KB-005"})
    assert "## Verification" in runbook.data["content"]


@pytest.mark.parametrize("limit", [0, 6, "3", True])
def test_search_limits_are_bounded_strict_integers(seeded_db, limit):
    _, ctx, tools = setup(seeded_db)
    result = tools.call(ctx, "search_knowledge", {"query": "vpn", "limit": limit})
    assert result.status == "error" and result.error.code == "INVALID_ARGUMENTS"
