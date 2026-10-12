"""Probe configured model tool calling without exposing credentials or raw errors."""

from pathlib import Path
from helpdesk.bootstrap.settings import Settings
from helpdesk.models.client import CompatibleChatModel, ModelFailure


def main():
    settings = Settings.load(Path(__file__).resolve().parents[1])
    model = CompatibleChatModel(settings)
    schema = {"name": "demo_probe", "description": "Confirm basic tool calling", "parameters": {"type": "object", "properties": {"ready": {"type": "boolean"}}, "required": ["ready"], "additionalProperties": False}}
    try:
        result = model.respond([{"role": "user", "content": "Call demo_probe with ready=true. Do not answer with plain text."}], [schema])
    except ModelFailure as exc:
        print(str(exc))
        raise SystemExit(1)
    import json
    if not result.calls or result.calls[0].name != "demo_probe" or json.loads(result.calls[0].arguments).get("ready") is not True:
        print("Model responded but did not satisfy the tool-calling probe.")
        raise SystemExit(1)
    print(f"Configured model tool calling OK; input_tokens={result.input_tokens}, output_tokens={result.output_tokens}.")


if __name__ == "__main__":
    main()
