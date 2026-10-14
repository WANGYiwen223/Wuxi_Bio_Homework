# Implementation Plan

Each milestone ended with a concrete acceptance check. Dependency order: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (steps 3 and 4 were separable after contracts stabilized, but actions could not run before authorization).

| Step | Work | Main locations | Acceptance result | Status |
|---|---|---|---|---|
| 0 | Module ownership, fixtures, scenarios, validation, isolated SQLite seeds. | `src/helpdesk/`, `data/`, `scripts/` | Fixtures/scenarios validate; independent databases seed without altering fixtures (3 tests). | Complete |
| 1 | Pydantic contracts, trusted ToolContext, clock, case lifecycle, repositories. | `domain/`, `storage/`, `bootstrap/` | Identity isolation, source timestamps, explicit missing/error results, restart continuity (6 tests). | Complete |
| 2 | Read tools and lexical KB/history retrieval. | `tools/`, `adapters/`, `knowledge/` | Source IDs and scoped data; the same VPN symptom retrieves competing explanations (11 tests). | Complete |
| 3 | Deterministic policy decisions and approval storage. | `policy/`, `storage/` | PROD grant waits for scoped approval; deny overrides allow; absent rule fails closed (13 tests). | Complete |
| 4 | LangGraph diagnostic loop with model-selected tools and clarification. | `workflow/`, `models/` | Multi-turn facts persist; tool failures and budgets terminate usefully; strict action schemas; interrupted-call reconciliation (29 tests + live tool-calling probe). | Complete |
| 5 | Mock actions, idempotency, independent verification. | `resolution/` | Unlock changes current state; VPN refresh cannot fix an outage; replay does not duplicate a grant (6 tests). | Complete |
| 6 | Contextual human handoff and durable reviewer queue. | `escalation/`, `storage/` | Handoff preserves evidence/attempts; creation is distinct from acknowledgement (2 tests). | Complete |
| 7 | FastAPI and minimal employee/reviewer interface. | `api/`, `ui/` | Session identity and reviewer role backend-bound; employee can converse, give feedback, see pending status (4 API tests; browser QA pending). | Complete |
| 8 | Conversation evaluations, traces, interview demo. | `evaluation/`, `observability/`, `tests/` | Report verified resolutions, appropriate escalations, failures, latency, usage (2 scoring tests; version-2 14-trial live matrix saved with 13 of 14 passing; version-1 outcomes retained in [EVALUATION.md](EVALUATION.md)). | Implemented; provider reliability and browser QA open |

Do not expand to voice, MCP, vector databases, or real enterprise integrations before the local conversation and execution boundaries pass acceptance. Scenario expectations are test oracles, never instructions to the agent. Read-tool caching must honor freshness; write retries need idempotency and reconciliation.

Run the complete current suite with `.venv/Scripts/python.exe -m pytest -q` — **121 passed as of 2026-10-14**. See [progress and open validation items](PROGRESS.md).
