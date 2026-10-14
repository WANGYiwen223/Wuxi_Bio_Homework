"""Completion shape is validated independently of provider availability."""

from types import SimpleNamespace

from openai.types.chat import ChatCompletion
import pytest

from helpdesk.bootstrap.settings import Settings
from helpdesk.models.client import CompatibleChatModel, ModelReply, ToolCall


def test_adapter_preserves_completion_metadata_without_reasoning_text(tmp_path, monkeypatch):
    calls = []
    response = ChatCompletion.model_validate({
        "id": "test-completion", "object": "chat.completion", "created": 0, "model": "fixture",
        "choices": [{"index": 0, "finish_reason": "length", "message": {
            "role": "assistant", "content": None, "reasoning_content": "private-reasoning-must-not-persist",
        }}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 1800, "total_tokens": 2100,
                  "completion_tokens_details": {"reasoning_tokens": 1800}},
    })

    def create(**kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr("helpdesk.models.client.OpenAI", lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    settings = Settings(base_url="https://example.test/v1", api_key="test", model_name="fixture", run_dir=tmp_path,
                        model_max_tokens=1800, model_recovery_max_tokens=4096)
    model = CompatibleChatModel(settings)
    result = model.respond([], [])
    assert result.response_error == "model_output_truncated"
    assert result.finish_reason == "length" and result.reasoning_tokens == 1800
    assert result.input_tokens == 300 and result.output_tokens == 1800
    assert "private-reasoning" not in result.model_dump_json()
    model.respond([], [], max_output_tokens=4096)
    assert [c["max_tokens"] for c in calls] == [1800, 4096]


@pytest.mark.parametrize("reply,expected", [
    (ModelReply(), "model_empty_response"),
    (ModelReply(text=" \n\t", finish_reason="stop"), "model_empty_response"),
    (ModelReply(text="unfinished answer", finish_reason="length"), "model_output_truncated"),
    (ModelReply(finish_reason="length", calls=[ToolCall(call_id="partial", name="propose_action", arguments="{}")]), "model_output_truncated"),
    (ModelReply(refused=True), "model_response_refused"),
    (ModelReply(finish_reason="content_filter"), "model_response_refused"),
    (ModelReply(finish_reason="tool_calls", calls=[ToolCall(call_id="valid", name="get_employee_context", arguments="{}")]), None),
    (ModelReply(text="Which application fails?", finish_reason="stop"), None),
])
def test_empty_truncated_refused_and_tool_only_responses_are_distinct(reply, expected):
    assert reply.response_error == expected


def test_output_limits_load_and_validate(tmp_path, monkeypatch):
    for key, value in {"HELPDESK_MODEL_BASE_URL": "https://example.test/v1", "HELPDESK_MODEL_API_KEY": "test",
                       "HELPDESK_MODEL_NAME": "fixture", "HELPDESK_MODEL_MAX_TOKENS": "1800",
                       "HELPDESK_MODEL_RECOVERY_MAX_TOKENS": "4096"}.items():
        monkeypatch.setenv(key, value)
    settings = Settings.load(tmp_path)
    assert settings.model_max_tokens == 1800 and settings.model_recovery_max_tokens == 4096
    monkeypatch.setenv("HELPDESK_MODEL_RECOVERY_MAX_TOKENS", "1000")
    with pytest.raises(ValueError, match="at least"):
        Settings.load(tmp_path)
    monkeypatch.setenv("HELPDESK_MODEL_MAX_TOKENS", "0")
    with pytest.raises(ValueError):
        Settings.load(tmp_path)
