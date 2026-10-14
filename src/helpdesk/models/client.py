"""OpenAI-compatible chat tool adapter. No provider exception bodies are exposed."""

from typing import Literal, Protocol

from openai import OpenAI, OpenAIError
from pydantic import Field

from helpdesk.domain.contracts import Contract


class ModelFailure(Exception):
    def __init__(self, message, category="model_error"):
        super().__init__(message)
        self.category = category


class ToolCall(Contract):
    call_id: str
    name: str
    arguments: str


class ModelReply(Contract):
    text: str = ""
    calls: list[ToolCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = Field(default=None, ge=0)
    finish_reason: Literal["stop", "length", "tool_calls", "function_call", "content_filter", "unknown"] | None = None
    refused: bool = False

    @property
    def response_error(self) -> str | None:
        if self.refused or self.finish_reason == "content_filter":
            return "model_response_refused"
        if self.finish_reason == "length":
            # A truncated tool batch must not execute even apparently complete calls.
            return "model_output_truncated"
        if not self.calls and not self.text.strip():
            return "model_empty_response"
        return None


class ChatModel(Protocol):
    def respond(self, messages: list[dict], schemas: list[dict], *, max_output_tokens: int | None = None) -> ModelReply:
        """Return model-selected tool calls or assistant content."""


class CompatibleChatModel:
    def __init__(self, settings):
        self.model_name = settings.model_name
        self.max_output_tokens = settings.model_max_tokens
        self.client = OpenAI(api_key=settings.api_key.get_secret_value(), base_url=settings.base_url, timeout=settings.timeout, max_retries=0)

    def respond(self, messages, schemas, *, max_output_tokens=None):
        try:
            response = self.client.chat.completions.create(model=self.model_name, messages=messages, tools=[{"type": "function", "function": schema} for schema in schemas], tool_choice="auto", max_tokens=max_output_tokens if max_output_tokens is not None else self.max_output_tokens)
            choice = response.choices[0]
            message = choice.message
            calls = [ToolCall(call_id=c.id, name=c.function.name, arguments=c.function.arguments) for c in message.tool_calls or []]
            usage = response.usage
            details = getattr(usage, "completion_tokens_details", None)
            finish = choice.finish_reason
            if finish not in {None, "stop", "length", "tool_calls", "function_call", "content_filter"}:
                finish = "unknown"
            return ModelReply(text=message.content or "", calls=calls, input_tokens=usage.prompt_tokens if usage else 0, output_tokens=usage.completion_tokens if usage else 0,
                              reasoning_tokens=getattr(details, "reasoning_tokens", None), finish_reason=finish, refused=bool(getattr(message, "refusal", None)))
        except (OpenAIError, IndexError, AttributeError, ValueError) as exc:
            # Do not copy str(exc): remote responses can echo secrets and prompts.
            raise ModelFailure(f"Model request failed ({type(exc).__name__})", type(exc).__name__) from None
