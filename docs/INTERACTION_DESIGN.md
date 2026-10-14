# Employee interaction and developer observability

The employee should be able to answer three questions: what is happening now, what was found, and what do I need to do next? Developers need a separate view that explains a slow or failed request without reading database tables manually.

## Three surfaces

| Surface | Content | Example |
|---|---|---|
| Chat | Finding, uncertainty where relevant, practical next step; at most two questions | “Your account is locked [1]. I can unlock the simulated account with your permission.” |
| Investigation | Actual execution progress, completion/error state, elapsed duration, expandable source cards | “Check service health and incidents — completed”; “[1] OKTA · Account state” |
| Developer diagnostics | Committed event metadata, turn/call IDs, internal evidence mapping, tokens, durations, error categories | `model_started` → `tool_started` → `tool_completed` → `turn_completed` |

The investigation panel reports observable work — not model reasoning, a generated plan presented as completed work, or a guessed percentage. A successful read means data was obtained, not that the service is healthy or the issue is fixed. Proposals, consent, approval, execution, verification, and employee confirmation remain distinct, as do queued and acknowledged handoffs.

## Evidence references

Internal evidence IDs bind tool results to actions and policy checks; the model cites one in an answer as `[[EVID-...]]`, and the application resolves it to a stable case-local number such as `[1]`. Clicking opens the source card with its title, selected facts, source time, and version. Plain/backtick/bracketed IDs and legacy source keys in previously saved messages are also resolved; repeated reads of an identical snapshot share a display number while keeping separate audit records. A missing or fabricated evidence ID becomes `[source unavailable]`, never a clickable source. Citation existence is checked; semantic support for a claim still requires model-quality evaluation. Employee input is displayed as entered (after secret redaction); the UI builds text nodes, not model-supplied HTML.

## Delivery and recovery

The synchronous message endpoint runs in a worker thread, so committed activity can be read while the agent runs. The browser polls `/cases/{case_id}/activity?after=<cursor>` roughly every second while busy (three seconds otherwise), drains paginated events by SQLite sequence, updates running steps on completion, and refreshes case state. Poll failures show a reconnection notice; an unexpected turn failure records a terminal event without the original error body.

This is live execution progress, not token-by-token streaming. Source times use the configured synthetic clock; event `recorded_at` uses real UTC and durations use a monotonic clock. Restoring a browser session after reload and managing interrupted jobs across restarts are separate work; persisted events alone do not prove a worker is still running.

## Logs and access

Starting `helpdesk.api.main:app` configures JSON-line metadata logs on stderr and in `<HELPDESK_RUN_DIR>/app.log` (2 MB rotation, three backups). Only committed audit events are logged: model/tool starts and completions, turn/call IDs, elapsed milliseconds, usage, and sanitized error categories. Prompts, tool arguments, tool result bodies, and provider exception bodies are not logged.

The collapsed developer panel reads `/cases/{case_id}/diagnostics` only when open. Activity and diagnostics enforce the same case/session ownership checks as the case API; the inspector is part of this loopback-only demo, not a production developer role.

## Validation

Integration coverage includes concurrent activity reads while the model is blocked, cross-employee/session rejection, incremental cursors, valid and unknown citations, saved-message rendering, duplicate snapshots, skipped/invalid tools, unexpected failures, and log suppression for rolled-back transactions. The deterministic suite passed 121 tests on 2026-10-14; API-level checks with scripted models drive the same endpoints the browser polls, confirming in-flight progress visibility and citation-to-source-number resolution. Automated browser interaction QA has not run on this host (see [EVALUATION.md](EVALUATION.md)). These do not establish citation quality for all real-model responses.
