# Evaluation

## Data version 2 — 2026-10-14

Scenarios no longer contain a default employee: `baseline` is a healthy control and the account problem is `account_lockout`. Reusable personal conditions are injected into selected employees; shared incidents keep their scope. The default `mixed_issues` environment contains overlapping account and VPN faults plus a shared pipeline incident.

`tests/conversations/expected_outcomes.json` selects two actors per problem type — 14 independent trials, each from its own database. Use `scripts/run_evaluation.py --list` to inspect the matrix without provider calls, or `--scenarios pipeline_maintenance --employees EMP-001` to filter a live run. Expectations and assignments are never privileged model instructions. Offline tests cover fault injection for all eight employees, overlapping faults, independent repairs, shared diagnostic access, and department/location-dependent decisions. The version-2 live matrix has been run (results below); the version-1 live results further down are retained as historical evidence.

Validation on 2026-10-14: **121 tests passed in ~11–15 seconds**; all nine scenarios, 14 articles, seven action rules, and fixture references validated; JavaScript syntax and generated SQLite integrity checks passed. Tests used scripted models and no provider calls.

## Method

Deterministic unit/integration tests validate state transitions, identity isolation, provenance, error handling, policy precedence, approval scope/expiry, transactional idempotency, verification, contextual handoff, and API boundaries. Scripted model doubles do not establish model quality.

`scripts/run_evaluation.py` uses the configured real model with synthetic employee feedback and reviewer decisions. Scenario names, expected checks, evaluator prompts, and fault definitions are not sent as privileged model instructions. The scorer checks persisted effects rather than assistant success claims. Reports include final status, check outcomes, elapsed seconds, model/tool call counts, and tokens; no monetary cost is claimed without provider pricing. Full fictional transcripts are kept locally for failure analysis.

## Observed failures and repairs

Initial live trials for account unlock and stale VPN failed because the broad action schema left target IDs and parameters ambiguous; the backend refused them and did not bypass policy. The model-visible schema now constrains operation/resource/environment values and exposes only device ID, access role, and business justification; consent and identity cannot be supplied as parameters. Repeated calls are compared by result fingerprints, and interrupted tool exchanges are reconciled against durable proposal/action records without replaying side effects.

After these changes, live account unlock, stale VPN, and combined Snowflake/Grafana trials passed observable outcome checks (3, 4, and 5 model calls). A later account-unlock trial failed at the provider boundary before obtaining evidence. These are individual synthetic trials, not an estimated production resolution rate.

## Live matrix results (data version 2) — 2026-10-14

All seven scenarios with both actors in one run (`var/evaluation/live-aadcbca1.json`, fixture version 2.0; real model with synthetic employee feedback and reviewer decisions; each trial from its own database): **13 of 14 trials passed**. Totals: 74 model calls, 125 tool calls, 964.82 seconds, 493,882 input / 31,176 output tokens; no trial hit a provider/turn failure.

| Scenario | Employees | Outcome | Final status | Model calls |
|---|---|---|---|---:|
| Account lockout | EMP-001, EMP-003 | Both passed | resolved | 6, 4 |
| Stale VPN profile | EMP-001, EMP-004 | Both passed: refresh verified and confirmed | resolved | 4, 4 |
| Regional VPN outage | EMP-002, EMP-004 | Both passed: contextual handoff, no mutation | escalated | 6, 6 |
| Snowflake PROD + Grafana access | EMP-001, EMP-004 | Both passed: grants verified; PROD approval recorded | resolved | 6, 6 |
| Pipeline after maintenance | EMP-001, EMP-004 | Both passed: evidence-preserving SRE handoff | escalated | 3, 4 |
| Conflicting VPN evidence | EMP-002, EMP-004 | EMP-002 passed; **EMP-004 failed** | escalated / awaiting_employee | 6, 10 |
| Tool timeout | EMP-001, EMP-004 | Both passed: bounded recovery after injected timeouts | resolved | 4, 5 |

The failed `conflicting_evidence` trial (EMP-004) ended `awaiting_employee` after five turns (10 model calls, 164.79 seconds), failing the `appropriate_handoff` check; its other checks (multiple sources, no unauthorized mutation) passed. The failure is retained in the report rather than hidden by the other thirteen passes. These remain synthetic trials, not a production resolution rate.

## Live trial results (data version 1)

Historical evidence only: the report files referenced below are no longer present on this machine; the aggregated outcomes are retained for the audit trail.

The most recent saved trial per scenario — separate runs, not one simultaneous benchmark:

| Scenario | Latest result | Final status | Model calls | Seconds | Report |
|---|---|---|---:|---:|---|
| Account unlock (`baseline`) | Failed: model unavailable before tool use | escalated | 1 | 22.67 | `var/evaluation/live-6a765a3c.json` |
| Stale VPN profile | Passed: verified simulated refresh and employee confirmation | resolved | 4 | 32.33 | `var/evaluation/live-6a765a3c.json` |
| Regional VPN outage | Passed: contextual handoff without mutation | escalated | 5 | 89.20 | `var/evaluation/live-0f21b910.json` |
| Snowflake PROD + Grafana access | Passed: both grants verified; PROD approval recorded | resolved | 6 | 58.08 | `var/evaluation/live-6a765a3c.json` |
| Pipeline after maintenance | Passed: change/build evidence and contextual SRE handoff | escalated | 3 | 31.46 | `var/evaluation/live-349cdfde.json` |
| Conflicting VPN evidence | Passed outcome checks; a later model failure triggered handoff | escalated | 3 | 61.27 | `var/evaluation/live-0f21b910.json` |
| Tool timeout | Passed outcome checks: timeout and partial evidence preserved; later model failure | escalated | 4 | 59.65 | `var/evaluation/live-0f21b910.json` |

Account unlock previously passed in `live-60c39818.json` (3 calls, 28.47 s); the later failure is retained to prevent claiming all latest trials passed. A passing fallback/handoff check does not establish a complete diagnosis.

## Pipeline maintenance retest — 2026-10-12

`scripts/run_evaluation.py --scenarios pipeline_maintenance --max-turns 5` with the unchanged 60-second request timeout passed all six outcome checks: the case was escalated to the SRE queue with no action records and no model failure. Persisted evidence: `change:CHG-001` (Friday maintenance rotated ETL credentials and updated the production allowlist), `diagnostic:BUILD-001` (PROD Jenkins failing since 21:15 with Snowflake timeouts, no auth error), `diagnostic:REPORT-001` (stale Tableau dashboard depending on Jenkins), current service observations, `knowledge:KB-010`/`KB-011`, and two competing historical causes. The handoff treated the maintenance correlation as a hypothesis, and one `NOT_FOUND` diagnostic lookup was retained rather than presented as success.

Measured usage: **3 model calls, 13 tool calls, 31.46 seconds, 19,957 input / 1,300 output tokens**. Earlier pipeline trials failed before tool use at ~40 and ~62 seconds (`APITimeoutError`); their reports are retained. This retest shows the scenario can complete with the current provider, but repeated-run reliability is unestablished. Regression check after the retest: full suite passed with no code changes.

## Interface QA

API/static-page tests and a JavaScript syntax check passed. The integrated browser automation tool could not initialize on this Windows host (sandbox helper error), so automated visual/interaction QA is not claimed; the local demo page is available for manual inspection.
