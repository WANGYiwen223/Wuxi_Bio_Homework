# Synthetic Demo Data

All records are fictional. `example.test` addresses are non-delivery identifiers.

- `knowledge/`: 14 Markdown procedures and metadata index.
- `fixtures/`: eight employees and devices, seven services, three access resources, account/device/build observations, changes, and nine historical resolutions.
- `policies/`: declarative exact-match authorization rules evaluated by `src/helpdesk/policy/engine.py`; the implemented executor re-evaluates current authority inside the mutation transaction.
- `scenarios/`: deterministic clock, per-record overrides and fault configuration, kept outside model context.

Baseline: EMP-003 has a locked Okta account; EMP-004 has a stale VPN profile; services are healthy. The directory account is active while the Okta account is temporarily locked: these represent employment/directory state and service login state respectively.

Overrides merge top-level record fields by each collection's primary key; nested objects such as observations are replaced in full. New records require complete fields. Scenarios start from baseline, never from another scenario.

Policies default to deny; deny overrides approval, which overrides allow. Facts must be trusted, missing conditions cannot match, and manager approval means the employee's directory manager.

Run `python scripts/demo_data.py validate` and `python scripts/demo_data.py seed --scenario baseline`. The seed database uses keyed JSON payloads for mock source rows. `Repository` adds trusted session storage, case ownership and optimistic revision columns when opened. Expected behavior lives in `tests/conversations/expected_outcomes.json` and must never enter agent context. `ReadTools` implements scenario timeout injection with persisted per-case counters; runtime composition must pass in the scenario fault configuration.
