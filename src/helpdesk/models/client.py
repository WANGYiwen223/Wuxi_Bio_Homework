"""OpenAI-compatible chat tool adapter. No provider exception bodies are exposed."""

from typing import Protocol

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


class ChatModel(Protocol):
    def respond(self, messages: list[dict], schemas: list[dict]) -> ModelReply:
        """Return model-selected tool calls or assistant content."""


class CompatibleChatModel:
    def __init__(self, settings):
        self.model_name = settings.model_name
        self.client = OpenAI(api_key=settings.api_key.get_secret_value(), base_url=settings.base_url, timeout=settings.timeout, max_retries=0)

    def respond(self, messages, schemas):
        try:
            response = self.client.chat.completions.create(model=self.model_name, messages=messages, tools=[{"type": "function", "function": schema} for schema in schemas], tool_choice="auto", max_tokens=1800)
            message = response.choices[0].message
            calls = [ToolCall(call_id=c.id, name=c.function.name, arguments=c.function.arguments) for c in message.tool_calls or []]
            usage = response.usage
            return ModelReply(text=message.content or "", calls=calls, input_tokens=usage.prompt_tokens if usage else 0, output_tokens=usage.completion_tokens if usage else 0)
        except (OpenAIError, IndexError, AttributeError, ValueError) as exc:
            # Do not copy str(exc): remote responses can echo secrets and prompts.
            raise ModelFailure(f"Model request failed ({type(exc).__name__})", type(exc).__name__) from None
