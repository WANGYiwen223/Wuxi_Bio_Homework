# Employee interaction and developer observability

The employee should be able to answer three questions: what is happening now, what
was found, and what do I need to do next? Developers need a separate view that can
explain a slow or failed request without reading database tables manually.

## Three surfaces

| Surface | Content | Example |
|---|---|---|
| Chat | Finding, uncertainty where relevant, practical next step; at most two questions | “Your account is locked [1]. I can unlock the simulated account with your permission.” |
| Investigation | Actual execution progress, completion/error state, elapsed duration, expandable source cards | “Check service health and incidents — completed”; “[1] OKTA · Account state” |
| Developer diagnostics | Committed event metadata, turn/call IDs, internal evidence mapping, tokens, durations and error categories | `model_started` → `tool_started` → `tool_completed` → `turn_completed` |

The investigation panel reports observable work. It is not model reasoning, a
generated plan presented as completed work, or a guessed percentage. A successful
read means data was obtained, not that the service is healthy or the issue is fixed.
Proposals, permission, manager approval, execution, verification and employee
confirmation remain distinct. Queued and acknowledged handoffs remain distinct.

## Evidence references

Internal evidence IDs continue to bind tool results to actions and policy checks.
The model receives them and uses them unchanged in tool arguments. In an answer,
it can cite a returned ID with `[[EVID-...]]`. The application resolves that marker
to a stable case-local number such as `[1]`. Clicking it opens the source card with
its descriptive title, selected facts, source time and version.

The presentation layer also handles plain/backtick/bracketed IDs and legacy source
keys in previously saved assistant messages. Original messages and checkpoints
retain the original IDs. Repeated reads of an identical source snapshot share a
display number but retain separate audit records; changed snapshots get a new
number. Legacy source keys without a snapshot ID resolve to their first recorded
snapshot. A missing or fabricated evidence ID becomes `[source unavailable]`,
never a clickable source. Citation existence is checked; semantic support for a
claim still requires model-quality evaluation.

Employee input is displayed as entered after existing secret redaction; it is not
rewritten as assistant citations. The UI builds text nodes, not model-supplied HTML.

## Delivery and recovery

The existing synchronous message endpoint is retained. FastAPI runs it in a worker
thread, allowing authenticated reads of committed activity while the agent runs.
The browser polls `/cases/{case_id}/activity?after=<cursor>` roughly every second
while busy and every three seconds otherwise. It drains paginated events by their
SQLite sequence, updates existing running steps on completion, and refreshes case
state to show messages, evidence and later reviewer decisions. Poll failures show
a reconnection notice. An unexpected turn failure records a terminal event; the
original error body is not included in telemetry.

This is live execution progress, not token-by-token answer streaming. Source times
use the configured synthetic clock; event `recorded_at` uses real UTC time and
durations use a monotonic clock. Polling survives a temporary connection failure.
Restoring a browser session after reload and managing interrupted jobs across
process restarts are separate work; persisted events alone do not prove a worker
is still running.

## Logs and access

Starting `helpdesk.api.main:app` configures JSON-line metadata logs on stderr and in
`<HELPDESK_RUN_DIR>/app.log` (2 MB rotation, three backups). Only committed audit
events are logged. A request includes model/tool starts and completions, a turn ID,
call IDs, elapsed milliseconds, usage and sanitized error categories. The final
turn event includes its case status and failure category when applicable. Policy,
consent, execution, verification and handoff events use the same audit/log path.
Prompts, tool arguments, tool result bodies and provider exception bodies are not
logged. Source mapping remains in the case evidence records.

The collapsed developer panel reads `/cases/{case_id}/diagnostics` only when open.
Both activity and diagnostics enforce the same case/session ownership checks as
the existing case API. The inspector is part of this loopback-only demo, not a new
production developer authorization role. Production use would need separate
operator access and log retention controls.

## Validation

Integration coverage includes concurrent activity reads while the model is blocked,
cross-employee and cross-session rejection, incremental cursors, valid and unknown
citations, saved-message rendering, duplicate source snapshots, skipped/invalid
tools, unexpected failures, and suppressing logs for rolled-back transactions.
The deterministic suite passed 62 tests on 2026-10-13. Browser checks with an
isolated scripted model confirmed in-flight progress and clickable source expansion.
These checks do not establish citation quality for all real-model responses.
