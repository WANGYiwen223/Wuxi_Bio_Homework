"""Inspect completion metadata on a public arithmetic/tool-calling request.

Makes real model calls but never executes returned tools. Saves only response
shape, usage and request hashes: no credentials, content or reasoning text.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from openai import OpenAI, OpenAIError

from helpdesk.bootstrap.settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', help='Defaults to the configured model; never modifies .env')
    parser.add_argument('--limits', default='1,1800', help='Comma-separated output token caps')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    caps = [int(value) for value in args.limits.split(',')]
    if not caps or any(not 1 <= cap <= 32768 for cap in caps) or len(caps) > 3:
        parser.error('Use one to three caps between 1 and 32768')
    root = Path(__file__).resolve().parents[1]
    settings = Settings.load(root)
    model_name = args.model or settings.model_name
    folder = root / 'var' / ('f12-output-' + uuid4().hex[:8])
    folder.mkdir(parents=True)
    # Deliberately independent of project prompts, employees, data and tools.
    messages = [{'role': 'user', 'content': 'Compute 17 multiplied by 19, then call report_answer with the integer result.'}]
    schemas = [{'type': 'function', 'function': {'name': 'report_answer', 'description': 'Report an arithmetic result.',
                'parameters': {'type': 'object', 'properties': {'answer': {'type': 'integer'}}, 'required': ['answer'], 'additionalProperties': False}}}]
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    report = {'model': model_name, 'created_at': datetime.now(timezone.utc).isoformat(),
              'request_hash': digest(messages), 'schema_hash': digest(schemas), 'responses': []}
    path = folder / 'model-output-metadata.json'
    with OpenAI(api_key=settings.api_key.get_secret_value(), base_url=settings.base_url, timeout=args.timeout, max_retries=0) as client:
        for cap in caps:
            started = time.monotonic()
            item = {'max_tokens': cap}
            try:
                response = client.chat.completions.create(model=model_name, messages=messages, tools=schemas, tool_choice='auto', max_tokens=cap)
                choice = response.choices[0]
                usage = response.usage
                details = getattr(usage, 'completion_tokens_details', None)
                item.update(finish_reason=choice.finish_reason, content_chars=len(choice.message.content or ''),
                            tool_calls=len(choice.message.tool_calls or []), refusal=bool(getattr(choice.message, 'refusal', None)),
                            reasoning_chars=len(getattr(choice.message, 'reasoning_content', '') or ''),
                            input_tokens=usage.prompt_tokens if usage else None,
                            output_tokens=usage.completion_tokens if usage else None,
                            reasoning_tokens=getattr(details, 'reasoning_tokens', None))
            except (OpenAIError, IndexError, AttributeError, ValueError) as error:
                item['error_type'] = type(error).__name__
            item['duration_ms'] = round((time.monotonic() - started) * 1000)
            report['responses'].append(item)
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps({'model': model_name, **item}), flush=True)
    print(f'Metadata report: {path}', flush=True)
    if any('error_type' in item for item in report['responses']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
