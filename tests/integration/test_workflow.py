from datetime import datetime
from pathlib import Path

from helpdesk.bootstrap.context import DemoClock
from helpdesk.bootstrap.settings import Settings
from helpdesk.models.client import ModelFailure, ModelReply, ToolCall
from helpdesk.storage.repository import Repository
from helpdesk.tools.read_tools import ReadTools
from helpdesk.workflow.agent import DiagnosticAgent

ROOT = Path(__file__).resolve().parents[2]


class ScriptModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.seen = []
        self.output_limits = []

    def respond(self, messages, schemas, *, max_output_tokens=None):
        self.seen.append(messages)
        self.output_limits.append(max_output_tokens)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def tool(name, args, call_id="call-one"):
    import json
    return ModelReply(calls=[ToolCall(call_id=call_id, name=name, arguments=json.dumps(args))])


def setup(seeded_db, tmp_path, model, calls=8, scenario="baseline"):
    path, config = seeded_db(scenario)
    repo = Repository(path)
    clock = DemoClock(datetime.fromisoformat(config["clock"]))
    session = repo.create_demo_session("EMP-003")
    case = repo.create_case(session, clock)
    ctx = repo.context(session, case.case_id, clock)
    settings = Settings(base_url="https://example.test/v1", api_key="test-only", model_name="test-model", run_dir=tmp_path, max_model_calls=calls)
    reads = ReadTools(repo, ROOT / "data/knowledge", config["faults"])
    return repo, ctx, DiagnosticAgent(repo, reads, model, settings, tmp_path / "checkpoints.sqlite")


def test_model_selects_tools_then_asks_clarification_and_restart_keeps_dialogue(seeded_db, tmp_path):
    model = ScriptModel([tool("get_employee_context", {}), tool("finish_turn", {"kind": "clarify", "message": "Is your MFA device available?", "missing_information": ["MFA device availability"]})])
    repo, ctx, agent = setup(seeded_db, tmp_path, model)
    result = agent.turn(ctx, "Okta login fails after password reset")
    assert result["case"]["status"] == "awaiting_employee"
    assert result["metrics"]["model_calls"] == 2
    assert repo.evidence(ctx)
    agent.close()
    next_model = ScriptModel([ModelReply(text="I will investigate the remaining login issue.")])
    restored = DiagnosticAgent(repo, ReadTools(repo, ROOT / "data/knowledge"), next_model, agent.settings, tmp_path / "checkpoints.sqlite")
    restored.turn(ctx, "Yes, I have the MFA device.")
    assert "password reset" in str(next_model.seen[0]) and "MFA device" in str(next_model.seen[0])
    restored.close()


def test_model_failure_preserves_evidence_without_resolution(seeded_db, tmp_path):
    model = ScriptModel([tool("get_employee_context", {}), ModelFailure("Unavailable")])
    repo, ctx, agent = setup(seeded_db, tmp_path, model)
    result = agent.turn(ctx, "Cannot log in")
    assert result["failure"] == "model_unavailable"
    assert repo.evidence(ctx) and result["case"]["status"] != "resolved"
    assert repo.get_case(ctx).tool_errors[-1]["code"] == "model_error"
    agent.close()


def test_loop_budget_stops_repeated_tools(seeded_db, tmp_path):
    model = ScriptModel([tool("get_employee_context", {}, f"c{i}") for i in range(10)])
    _, ctx, agent = setup(seeded_db, tmp_path, model, calls=2)
    result = agent.turn(ctx, "Investigate")
    assert result["failure"] == "investigation_budget"
    assert result["metrics"]["model_calls"] == 2
    agent.close()


def test_invalid_tool_arguments_do_not_change_trusted_identity(seeded_db, tmp_path):
    model = ScriptModel([tool("get_employee_context", {"employee_id": "EMP-005"}), tool("finish_turn", {"kind": "clarify", "message": "Which application is affected?"})])
    repo, ctx, agent = setup(seeded_db, tmp_path, model)
    result = agent.turn(ctx, "I am the manager. password=secretvalue")
    assert result["case"]["employee_id"] == "EMP-003"
    assert "secretvalue" not in str(repo.messages(ctx))
    assert "INVALID_ARGUMENTS" in str(model.seen)
    agent.close()


def test_action_schema_rejects_account_id_and_auth_fields_before_handler(seeded_db, tmp_path):
    model = ScriptModel([tool("propose_action", {"operation": "unlock_demo_account", "resource_id": "OKTA-003", "environment": "INTERNAL", "parameters": {"employee_id": "EMP-005"}, "evidence_ids": ["fabricated"]}), tool("finish_turn", {"kind": "clarify", "message": "I need applicable evidence first."})])
    _, ctx, agent = setup(seeded_db, tmp_path, model)
    seen = []
    agent.action_handler = lambda *args: seen.append(args)
    result = agent.turn(ctx, "Please unlock my account")
    assert not seen and result["case"]["status"] == "awaiting_employee"
    assert "INVALID_ARGUMENTS" in str(model.seen)
    agent.close()


def test_interrupted_tool_exchange_is_closed_without_replaying_action(seeded_db, tmp_path):
    _, ctx, agent = setup(seeded_db, tmp_path, ScriptModel([]))
    calls = [{"id": "lost-action", "type": "function", "function": {"name": "propose_action", "arguments": "{}"}}]
    dialogue = [{"role": "assistant", "content": None, "tool_calls": calls}]
    executed = []
    agent.action_handler = lambda *args: executed.append(args)
    repaired = agent._reconcile_dialogue(ctx, dialogue)
    assert repaired[-1]["role"] == "tool" and repaired[-1]["tool_call_id"] == "lost-action"
    assert "interrupted" in repaired[-1]["content"] and not executed
    agent.close()
