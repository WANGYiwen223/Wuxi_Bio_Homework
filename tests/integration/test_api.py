from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpdesk.api.app import create_app
from helpdesk.bootstrap.context import DemoClock
from helpdesk.bootstrap.settings import Settings
from helpdesk.bootstrap.runtime import Runtime
from helpdesk.models.client import ModelReply
from helpdesk.storage.repository import Repository
from helpdesk.domain.contracts import ActionRequest
from helpdesk.domain.lifecycle import transition
from test_workflow import ScriptModel, tool

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def application(seeded_db, tmp_path):
    path, config = seeded_db()
    runtime = Runtime(Repository(path), Settings(base_url="https://example.test/v1", api_key="test", model_name="test", run_dir=tmp_path), DemoClock(datetime.fromisoformat(config["clock"])), ROOT / "data/knowledge", ROOT / "data/policies/action_rules.json", tmp_path / "checkpoints.sqlite", ScriptModel([tool("finish_turn", {"kind": "clarify", "message": "Which application fails?"})]))
    with TestClient(create_app(runtime, ROOT / "ui")) as client:
        yield client, runtime


def login(client, employee="EMP-003"):
    token = client.post("/demo/sessions", json={"employee_id": employee}).json()["session_id"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_api_preserves_identity_and_static_ui_serves_safely(application):
    client, _ = application
    assert client.get("/").status_code == 200
    assert "IT Helpdesk" in client.get("/").text
    assert client.get("/.env").status_code == 404
    headers = login(client)
    case = client.post("/cases", json={}, headers=headers).json()
    response = client.post(f"/cases/{case['case_id']}/messages", json={"text": "Something is broken"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["case"]["employee_id"] == "EMP-003"
    assert "session_id" not in response.json()["case"]
    assert client.get(f"/cases/{case['case_id']}", headers=login(client, "EMP-001")).status_code == 403


def test_loopback_origin_role_and_consent_gates(application):
    client, _ = application
    assert client.post("/demo/sessions", json={"employee_id": "EMP-003"}, headers={"Origin": "https://attacker.test"}).status_code == 403
    assert client.get("/health", headers={"Host": "attacker.test"}).status_code == 403
    headers = login(client)
    assert client.get("/review/handoffs", headers=headers).status_code == 403
    case = client.post("/cases", json={}, headers=headers).json()
    assert client.post(f"/cases/{case['case_id']}/consent", json={"operation": "unlock_demo_account", "allow": True}, headers=headers).status_code == 409
    assert client.post(f"/cases/{case['case_id']}/feedback", json={"resolved": "true"}, headers=headers).status_code == 422


def test_approval_api_executes_only_scoped_grant_after_review(application):
    client, runtime = application
    headers = login(client, "EMP-001")
    case = client.post("/cases", json={}, headers=headers).json()
    ctx = runtime.context(headers["Authorization"][7:], case["case_id"])
    evidence = runtime.reads.call(ctx, "get_employee_context", {}).evidence_ids + runtime.reads.call(ctx, "get_runbook", {"article_id": "KB-008"}).evidence_ids
    result = runtime.resolution.handle_proposal(ctx, ActionRequest(operation="grant_demo_access", resource_id="snowflake-prod", environment="PROD", parameters={"role": "reader", "business_justification": "Reporting"}, evidence_ids=evidence), "one")
    assert result["status"] == "awaiting_approval"
    assert client.post(f"/review/approvals/{result['approval_id']}/decision", json={"approve": True}, headers=headers).status_code == 403
    manager = login(client, "EMP-005")
    assert len(client.get("/review/approvals", headers=manager).json()) == 1
    approved = client.post(f"/review/approvals/{result['approval_id']}/decision", json={"approve": True}, headers=manager)
    assert approved.status_code == 200
    assert runtime.repository.get_case(ctx).status == "awaiting_verification"
    assert client.post(f"/cases/{case['case_id']}/feedback", json={"resolved": True}, headers=headers).status_code == 200
    assert runtime.repository.get_case(ctx).status == "resolved"


def test_multi_resource_case_does_not_close_after_only_one_grant(application):
    client, runtime = application
    headers = login(client, "EMP-001")
    case = client.post("/cases", json={}, headers=headers).json()
    ctx = runtime.context(headers["Authorization"][7:], case["case_id"])
    current = runtime.repository.get_case(ctx)
    runtime.repository.save_case(ctx, transition(current, current.status, ctx.clock.now(), facts={"consent_operations": ["grant_demo_access"], "required_resources": ["snowflake-prod", "grafana-internal"]}))
    evidence = runtime.reads.call(ctx, "get_employee_context", {}).evidence_ids + runtime.reads.call(ctx, "get_runbook", {"article_id": "KB-009"}).evidence_ids
    result = runtime.resolution.handle_proposal(ctx, ActionRequest(operation="grant_demo_access", resource_id="grafana-internal", environment="INTERNAL", parameters={"role": "viewer"}, evidence_ids=evidence), "grafana")
    assert result["status"] == "success"
    response = client.post(f"/cases/{case['case_id']}/feedback", json={"resolved": True}, headers=headers)
    assert response.json()["verification"]["observations"]["remaining_resources"] == ["snowflake-prod"]
    assert runtime.repository.get_case(ctx).status == "investigating"
