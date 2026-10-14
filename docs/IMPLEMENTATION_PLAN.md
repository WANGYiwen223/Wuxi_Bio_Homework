# Implementation Plan

Each milestone ends with a concrete acceptance check. Status is intentionally separate from the architectural proposal.

| Step | Work | Main locations | Acceptance | Status |
|---|---|---|---|---|
| 0 | Establish module ownership, fixtures, scenarios, validation, and isolated SQLite seeds. | `src/helpdesk/`, `data/`, `scripts/` | All fixtures/scenarios validate; independent databases seed without altering fixtures. | Complete |
| 1 | Define Pydantic contracts, trusted ToolContext, clock, case lifecycle, and repositories. | `domain/`, `storage/`, `bootstrap/` | Identity isolation, source timestamps, explicit missing/error results, and repository restart continuity. | Complete — 6 tests passed |
| 2 | Implement read tools and lexical KB/history retrieval. | `tools/`, `adapters/`, `knowledge/` | Read tools return source IDs and scoped data; same VPN symptom retrieves competing explanations. | Complete — 11 tests passed |
| 3 | Implement deterministic policy decisions and approval storage. | `policy/`, `storage/` | PROD grant waits for scoped reviewer approval; deny overrides allow; absent rule fails closed. | Complete — 13 tests passed |
| 4 | Build the LangGraph diagnostic loop with model-selected tools and employee clarification. | `workflow/`, `models/` | Multi-turn facts persist; questions are focused; tool failures and budgets terminate usefully. | Complete — 29 tests and live tool-calling probe passed |
| 5 | Implement mock actions, idempotency, and independent outcome verification. | `resolution/` | Unlock changes current state; VPN refresh cannot fix an outage; replay does not duplicate a grant. | Complete — 6 tests; 13 approval regressions passed |
| 6 | Implement contextual human handoff and durable reviewer queue. | `escalation/`, `storage/` | Handoff preserves evidence/attempts; creation is distinct from acknowledgement. | Complete — 2 tests passed |
| 7 | Add FastAPI and a minimal employee/reviewer interface. | `api/`, `ui/` | Session identity and reviewer role are backend-bound; employee can converse, give feedback, and see pending status. | Complete — 4 API tests passed; browser QA pending |
| 8 | Run complete conversation evaluations, collect traces, and prepare the interview demo. | `evaluation/`, `observability/`, `tests/` | Report verified resolutions, appropriate escalations, failures, latency, and model/tool usage. | Implemented — seven scenarios evaluated; pipeline retest passed; provider reliability and browser QA remain open |

Dependency order: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Steps 3 and 4 may be developed separately after contracts are stable, but actions cannot run before authorization is implemented.

Do not expand to voice, MCP, vector databases, or real enterprise integrations before the local conversation and execution boundaries pass acceptance. Scenario expectations are test oracles, never instructions to the agent. Read-tool caching must honor freshness; write retries need idempotency and reconciliation.

## Test Evidence

- Step 0: `python -m pytest tests/unit/test_fixtures.py -q` — 3 passed (scenario isolation, ownership and timestamps).
- Step 1: `python -m pytest tests/unit/test_contracts.py tests/integration/test_repository.py -q` — 6 passed (validated lifecycle, identity isolation, optimistic revisions, restart continuity).
- Step 2: `python -m pytest tests/integration/test_read_tools.py -q` — 11 passed (source provenance, target scope, competing explanations, missing data, persistent fault counters, strict argument bounds).
- Step 3: `python -m pytest tests/integration/test_policy_approvals.py -q` — 13 passed (scope-bound approval, trusted reviewer identity, expiry/rejection, policy invalidation, evidence and consent gates).
- Step 4: project `.venv` model/settings/workflow tests — 29 passed, including strict action schemas and interrupted-call reconciliation; `scripts/check_model.py` confirmed configured-provider tool calling. This is a compatibility probe, not full live conversation evaluation.
- Step 5: `test_resolution.py` — 6 passed; approval regressions — 13 passed. Verified transactional effects, request/action idempotency, fresh authorization and negative-feedback continuation.
- Step 6: `test_handoff.py` — 2 passed; context-preserving, idempotent creation and specialist-role-scoped acknowledgement.
- Step 7: `test_api.py` — 4 passed; loopback/origin boundaries, employee ownership, approval-to-execution flow and partial multi-resource verification.
- Step 8: `test_scoring.py` — 2 passed. Seven live scenarios have saved reports; see `EVALUATION.md` for failures as well as successes. The pipeline-maintenance retest passed with persisted change/build/report evidence and an SRE handoff.

Run the complete current suite with `.venv/Scripts/python.exe -m pytest -q` — 83 passed as of 2026-10-14. See [progress and open validation items](PROGRESS.md).
