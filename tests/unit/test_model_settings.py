import pytest

from helpdesk.bootstrap.settings import Settings
from helpdesk.observability.redaction import redact
from helpdesk.models.client import CompatibleChatModel, ModelFailure


def test_custom_env_names_load_without_leaking_key(tmp_path, monkeypatch):
    for name in ["HELPDESK_MODEL_BASE_URL", "HELPDESK_MODEL_API_KEY", "HELPDESK_MODEL_NAME"]:
        monkeypatch.delenv(name, raising=False)
    key = "sample-private-api-value"
    (tmp_path / ".env").write_text(f"HELPDESK_MODEL_BASE_URL=https://example.test/v1\nHELPDESK_MODEL_API_KEY={key}\nHELPDESK_MODEL_NAME=provider-model\n", encoding="utf-8")
    settings = Settings.load(tmp_path)
    assert settings.model_name == "provider-model"
    assert key not in repr(settings) and key not in settings.model_dump_json()


def test_redaction_removes_explicit_secret_labels():
    assert "hunter2" not in redact("password=hunter2")
    assert "123456" not in redact("OTP:123456")
    assert "abcdef" not in redact("Bearer abcdef")


def test_provider_exception_does_not_echo_credentials(tmp_path):
    from openai import BadRequestError
    import httpx
    from types import SimpleNamespace
    settings = Settings(base_url="https://example.test/v1", api_key="private-provider-key", model_name="chosen-model", run_dir=tmp_path)
    model = CompatibleChatModel(settings)
    def fail(**kwargs):
        assert kwargs["model"] == "chosen-model"
        raise BadRequestError("private-provider-key echoed by upstream", response=httpx.Response(400, request=httpx.Request("POST", "https://example.test/v1")), body=None)
    model.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    with pytest.raises(ModelFailure) as error:
        model.respond([], [])
    assert "private-provider-key" not in str(error.value)
