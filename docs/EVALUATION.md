# Evaluation

## Data version 2 — 2026-10-14

Scenarios no longer contain a default employee. `baseline` is a healthy control; the account problem is now `account_lockout`. Reusable personal conditions are injected into selected employees, while shared service/resource incidents keep their scope. The default `mixed_issues` environment contains overlapping account and VPN faults and a shared pipeline incident.

The evaluation configuration in `tests/conversations/expected_outcomes.json` selects two actors per problem type, producing 14 independent trials. An employee can appear in multiple problem types. Use `scripts/run_evaluation.py --list` to inspect the matrix without provider calls, or filter a live run with `--scenarios pipeline_maintenance --employees EMP-001`. Reports include employee ID and fixture version. Each trial starts from its own database; expectations and assignments are never privileged model instructions.

Offline coverage includes fault injection for all eight employees, overlapping faults, independent repairs across employees, shared diagnostic access/revocation, department-dependent approval and location-dependent outage handling. Historical live results below used version 1 data and are retained as historical evidence, not a validation of the new matrix. The new live matrix has not yet been run.

Validation on 2026-10-14: **109 tests passed in 14.67 seconds**; all nine scenarios, 14 articles, seven action rules and fixture references validated; JavaScript syntax and generated SQLite integrity checks passed. On this Windows host, the full test suite required execution outside the sandbox because TestClient's local socketpair initialization was blocked. Tests used scripted models and no model-provider calls.

## Method

Deterministic unit/integration tests validate state transitions, identity isolation, source provenance, error handling, policy precedence, approval scope/expiry, transactional idempotency, verification, contextual handoff and API boundaries. Model doubles are explicitly scripted and do not establish model quality.

`scripts/run_evaluation.py` uses the configured real model with synthetic employee feedback and reviewer decisions. Each trial starts from an independent seeded database. Scenario names, expected checks, evaluator prompts and fault definitions are not sent as privileged model instructions. Backend tool results provide evidence, and the scorer checks persisted effects rather than assistant success claims.

Report fields include final status, check outcomes, elapsed seconds, model/tool call counts, and input/output tokens. No monetary cost is claimed without provider pricing. `repository.trace` records redacted metadata-only model/turn events; tool events refer to evidence IDs. Full fictional case transcripts are kept locally for failure analysis.

## Observed failures and repairs

The initial live trials for account unlock and stale VPN failed because the broad action schema left target IDs and parameter fields ambiguous. The backend refused unsupported fields and wrong resource IDs; it did not bypass policy to achieve a passing result.

The model-visible schema now constrains operation/resource/environment values and exposes only device ID, access role and business justification. Consent and identity cannot be supplied as operation parameters. Repeated calls are compared by result fingerprints so a successful retry after a timeout counts as fresh evidence. Interrupted tool exchanges are reconciled against durable proposal/action records without replaying side effects.

After these changes, live account unlock, stale VPN and combined Snowflake/Grafana access trials passed the observable outcome checks (3, 4 and 5 model calls respectively). A later account-unlock trial failed at the provider boundary before obtaining evidence. These are individual synthetic trials, not an estimated production resolution rate.

## Live trial results

The following table reports the most recent saved trial for each scenario, rather than selecting only successful trials. Trials were run separately; this table is not one simultaneous benchmark run.

| Scenario | Latest result | Final status | Model calls | Seconds | Report |
|---|---|---|---:|---:|---|
| Account unlock (`baseline`) | Failed: model unavailable before tool use | escalated | 1 | 22.67 | `var/evaluation/live-6a765a3c.json` |
| Stale VPN profile | Passed: verified simulated refresh and employee confirmation | resolved | 4 | 32.33 | `var/evaluation/live-6a765a3c.json` |
| Regional VPN outage | Passed: contextual handoff without mutation | escalated | 5 | 89.20 | `var/evaluation/live-0f21b910.json` |
| Production Snowflake and internal Grafana access | Passed: both grants verified; PROD approval recorded | resolved | 6 | 58.08 | `var/evaluation/live-6a765a3c.json` |
| Pipeline after maintenance | Passed: change/build evidence and contextual SRE handoff | escalated | 3 | 31.46 | `var/evaluation/live-349cdfde.json` |
| Conflicting VPN evidence | Passed outcome checks; a later model failure triggered handoff | escalated | 3 | 61.27 | `var/evaluation/live-0f21b910.json` |
| Tool timeout | Passed outcome checks: timeout and partial evidence preserved in handoff; later model failure | escalated | 4 | 59.65 | `var/evaluation/live-0f21b910.json` |

Account unlock previously passed in `live-60c39818.json` (3 calls, 28.47 seconds). Its later failure remains recorded and prevents claiming that the latest trials all passed. A passing fallback/handoff check does not establish a complete diagnosis or an automatic repair.

## Pipeline maintenance retest — 2026-10-12

Command: `.venv/Scripts/python.exe scripts/run_evaluation.py --scenarios pipeline_maintenance --max-turns 5`.

This retest used the current `.env` configuration, including a 60-second per-request timeout, without changing credentials or timeout settings. It created an independent run at `var/runs/eval-pipeline_maintenance-9fe71aa7/`. All six existing outcome checks passed. The case was escalated to the SRE queue, with no action records and no model failure. Queue creation does not mean that a specialist has acknowledged or repaired the incident.

The persisted evidence and handoff were inspected in addition to the aggregate score:

- `change:CHG-001`: Friday maintenance rotated ETL credentials and updated the production network allowlist, finishing at 21:00.
- `diagnostic:BUILD-001`: the PROD Jenkins job failed from 21:15 with Snowflake connection timeouts and no observed authentication error.
- `diagnostic:REPORT-001`: the Tableau dashboard last refreshed at 19:00 and depends on Jenkins.
- Current service observations: Jenkins and Tableau degraded; Snowflake healthy.
- `knowledge:KB-010` and `KB-011`: investigate upstream/downstream evidence and hand off production credential/network repair.
- Historical cases included both credential expiry and an allowlist regression. The handoff treated the maintenance correlation as a hypothesis and did not claim a confirmed root cause.

One diagnostic lookup returned `NOT_FOUND`; this was retained in the case and handoff instead of being presented as successful evidence. The model continued with the available Jenkins and Tableau diagnostics.

Measured usage: **3 model calls, 13 tool calls, 31.46 seconds, 19,957 input tokens, and 1,300 output tokens**. Earlier pipeline trials failed before tool use at approximately 40 and 62 seconds; the latter recorded `APITimeoutError`. Their reports (`live-0f21b910.json` and `live-3e22157d.json`) are retained. This successful retest shows that the scenario can complete with the current provider, while repeated-run reliability remains unestablished.

Regression check after the retest: `.venv/Scripts/python.exe -m pytest -q` — **56 passed in 11.68 seconds**. No application code changes were needed for this retest.

## Interface QA

API/static-page tests and a JavaScript syntax check passed. The integrated browser automation tool could not initialize due to the Windows sandbox helper error, so automated visual/interaction QA is not claimed. The local demo page is available for manual inspection.
