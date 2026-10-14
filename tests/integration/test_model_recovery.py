"""F12: bounded response recovery, no partial tools, no employee-facing loop."""

import json

import pytest

from helpdesk.escalation.service import HandoffService
from helpdesk.models.client import ModelReply, ToolCall
from test_workflow import ScriptModel, setup, tool


def test_empty_recovery_preserves_context_tools_usage_and_trace(seeded_db, tmp_path):
    model = ScriptModel([
        tool("get_employee_context", {}, "read-once"),
        ModelReply(finish_reason="length", input_tokens=100, output_tokens=1800, reasoning_tokens=1800),
        ModelReply(text="Is your MFA device available?", input_tokens=120, output_tokens=8),
    ])
    repo, ctx, agent = setup(seeded_db, tmp_path, model)
    try:
        result = agent.turn(ctx, "Okta is locked after password reset.")
        assert result["failure"] is None and result["message"] == "Is your MFA device available?"
        assert result["metrics"]["model_calls"] == 3 and result["metrics"]["tool_calls"] == 1
        assert result["metrics"]["input_tokens"] == 220 and result["metrics"]["output_tokens"] == 1808
        assert model.output_limits == [4096, 4096, 8192]
        # Recovery retains the completed tool exchange and the original question.
        assert any(m.get("tool_call_id") == "read-once" for m in model.seen[-1])
        assert "password reset" in str(model.seen[-1])
        assert not any(m["role"] == "assistant" and not m.get("content") and not m.get("tool_calls") for m in model.seen[-1])
        events = repo.events(ctx)
        assert len([e for e in events if e["event"] == "model_response_retry"]) == 1
        bad = next(e for e in events if e.get("response_error"))
        assert bad["finish_reason"] == "length" and bad["reasoning_tokens"] == 1800
        assert repo.get_case(ctx).tool_errors[-1]["code"] == "model_output_truncated"
    finally:
        agent.close()


@pytest.mark.parametrize("bad", [
    ModelReply(text=" \n"),
    ModelReply(finish_reason="length", calls=[ToolCall(call_id="do-not-execute", name="propose_action", arguments=json.dumps({
        "operation": "unlock_demo_account", "resource_id": "okta", "environment": "INTERNAL", "parameters": {}, "evidence_ids": ["test-evidence"],
    }))]),
])
def test_invalid_response_never_executes_partial_tools(seeded_db, tmp_path, bad):
    model = ScriptModel([bad, tool("finish_turn", {"kind": "clarify", "message": "Is MFA available?"})])
    _, ctx, agent = setup(seeded_db, tmp_path, model)
    executed = []
    agent.action_handler = lambda *args: executed.append(args)
    try:
        result = agent.turn(ctx, "Cannot sign in.")
        assert result["failure"] is None and not executed
        assert result["metrics"]["model_calls"] == 2 and result["metrics"]["tool_calls"] == 1
        assert "do-not-execute" not in str(model.seen[-1])
    finally:
        agent.close()


@pytest.mark.parametrize("calls,bad,expected_calls", [
    (8, ModelReply(), 2),
    (1, ModelReply(), 1),
    (8, ModelReply(finish_reason="length", output_tokens=1800, reasoning_tokens=1800), 2),
    (8, ModelReply(refused=True), 1),
    (8, ModelReply(finish_reason="content_filter"), 1),
])
def test_persistent_invalid_response_hands_off_and_cannot_loop_next_turn(seeded_db, tmp_path, calls, bad, expected_calls):
    model = ScriptModel([bad, bad])
    repo, ctx, agent = setup(seeded_db, tmp_path, model, calls=calls)
    agent.handoff_handler = HandoffService(repo).create
    try:
        result = agent.turn(ctx, "我的 Okta 无法登录，错误已经提供。")
        assert result["case"]["status"] == "escalated" and result["failure"] == bad.response_error
        assert result["metrics"]["model_calls"] == expected_calls
        assert result["metrics"]["tool_calls"] == 0
        assert "模型" in result["message"] and "人工支持" in result["message"]
        assert "Please describe the affected application and error." not in result["message"]
        with repo.transaction() as db:
            handoff = json.loads(db.execute("SELECT payload FROM handoffs").fetchone()[0])
        assert len(handoff["tool_errors"]) == expected_calls and "Okta" in handoff["issue_summary"]
        with pytest.raises(ValueError, match="closed"):
            agent.turn(ctx, "我已经回答过了")
        assert len(model.seen) == expected_calls
    finally:
        agent.close()


def test_recovery_allowance_does_not_reset_after_a_successful_tool(seeded_db, tmp_path):
    model = ScriptModel([ModelReply(), tool("get_employee_context", {}), ModelReply()])
    repo, ctx, agent = setup(seeded_db, tmp_path, model)
    agent.handoff_handler = HandoffService(repo).create
    try:
        result = agent.turn(ctx, "Cannot sign in.")
        assert result["failure"] == "model_empty_response" and result["case"]["status"] == "escalated"
        assert result["metrics"]["model_calls"] == 3 and result["metrics"]["tool_calls"] == 1
        assert repo.evidence(ctx)
        assert model.output_limits == [4096, 8192, 4096]
    finally:
        agent.close()


def test_legacy_empty_checkpoint_messages_are_removed(seeded_db, tmp_path):
    _, ctx, agent = setup(seeded_db, tmp_path, ScriptModel([]))
    try:
        dialogue = [{"role": "user", "content": "Original symptoms"}, {"role": "assistant", "content": None},
                    {"role": "user", "content": "More symptoms"}]
        assert agent._reconcile_dialogue(ctx, dialogue) == [dialogue[0], dialogue[2]]
    finally:
        agent.close()
