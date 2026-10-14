# Synthetic Demo Data / 合成数据

All records are fictional. `example.test` addresses are non-delivery identifiers.

员工身份、问题条件、评测用例分别建模。同类问题可发生在不同员工身上，同一员工可同时遇到账号、设备、权限或共享系统问题。员工编号不决定问题类型。

## Five source categories

| Source | Files | Scope |
|---|---|---|
| Knowledge base | `knowledge/`: 14 indexed Markdown articles, FAQs and runbooks | Reusable procedures selected by symptoms and applicability, never employee ID |
| System status | `fixtures/services.json`, `incidents.json`, `changes.json`, shared `diagnostic_snapshots.json` | Seven services; incidents scoped by location; changes and build/report observations scoped by service/resource |
| User directory | `fixtures/employees.json`, `devices.json`, `account_states.json`, `resources.json`, `access_grants.json` | Eight employees with departments, roles, locations, managers, equipment and permissions; private account/device state stays owned by its employee |
| Resolution history | `fixtures/resolution_history.json` | Nine searchable past resolutions with symptoms, causes, actions and verified outcomes; they do not prescribe a current answer |
| Policy / rules | `policies/action_rules.json`; shared-resource `diagnostic_readers` scopes | Seven action rules distinguish allowed operations, manager approval and denial; diagnostic access uses department/role scopes |

The five resources include three access-grant targets and two shared diagnostic targets. Account/device diagnostics complement directory and system observations.

## Healthy baseline and reusable conditions

`scripts/generate_demo_data.py` generates healthy fixture records: active Okta accounts, current VPN profiles and successful shared builds/reports. Knowledge, policy and scenario files are curated and are not overwritten by this generator.

```powershell
.\.venv\Scripts\python.exe scripts/generate_demo_data.py --overwrite
.\.venv\Scripts\python.exe scripts/demo_data.py validate
```

`scenarios/` contains environment templates with a fixed clock, personal `conditions`, shared-record `overrides` and tool `faults`. There is no scenario-level `employee_id`.

- `baseline`: healthy control environment; it no longer means account lockout.
- `account_lockout`: lock the selected employees' Okta accounts.
- `vpn_stale_profile`: make the selected employees' managed VPN profiles stale.
- `production_access`: healthy systems with directory permissions and existing grants; policies decide each request using the actual employee's department and manager.
- `vpn_regional_outage` / `conflicting_evidence`: a shared Chicago/Remote-US VPN incident, with fresh or conflicting status evidence, plus independently injected stale personal profiles. Location determines whether the outage applies.
- `pipeline_maintenance`: shared Jenkins build failure and stale Tableau report after a change window.
- `tool_timeout`: stale profiles plus bounded simulated status-tool timeouts.
- `mixed_issues` (default): four employees have locked accounts, five have stale profiles, and a shared pipeline/report incident exists. Counts overlap, so one employee can have several problems; missing application access can be requested independently.

Without `--employees`, personal conditions consider all eligible active employees. An optional `count` samples from that pool using `--random-seed` (default 42); conditions without a count affect the entire eligible pool. With fewer eligible employees than the count, all eligible employees are selected. Each selected employee's managed devices and matching observations are updated together. Shared incidents retain their region/resource scope regardless of `--employees`.

```powershell
# Default: multiple employees and multiple problems, reproducible sampling.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --run-id mixed-demo --random-seed 42

# Apply the SAME fault to different employees without editing source JSON.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --scenario account_lockout --employees EMP-001,EMP-002 --run-id account-demo
.\.venv\Scripts\python.exe scripts/demo_data.py seed --scenario vpn_stale_profile --employees EMP-001,EMP-003 --run-id vpn-demo

# The SAME employees have both personal faults plus the shared pipeline issue.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --scenario mixed_issues --employees EMP-001,EMP-004 --run-id combined-demo
```

Seeding prints personal fault assignments. The operator-only `manifest.json` records the seed, candidate employees and assignments; it does not choose a login identity. Runtime tools read factual state from SQLite, not these scenario labels or evaluation expectations. `ReadTools` implements configured timeouts with persisted per-case counters.

Every scenario starts from healthy fixtures. Shared overrides merge top-level fields by primary key; nested observations are replaced in full. New records require complete fields. Personal conditions are then materialized and all references validated. Existing run databases are never overwritten. To use new data, seed a fresh run, set `HELPDESK_RUN_DIR=var/runs/<run-id>` and restart the server. Existing runs retain their old data.

## Shared resources and identity boundaries

Private accounts and devices remain employee-owned. Jenkins `jenkins-sales-etl` and Tableau `tableau-sales-dashboard` observations have `employee_id: null`, `device_id: null` and a `resource_id`. Data Engineering employees and the IT reviewer can inspect them according to resource `diagnostic_readers`; other users cannot retrieve the detailed snapshots. Access is rechecked on every read. Shared observation facts are identical for authorized readers, while evidence and cases remain separately owned.

`get_employee_context` returns roles and authorized diagnostic resources alongside personal state. `get_diagnostic_snapshot` accepts an optional `device_id` or `resource_id` (mutually exclusive). Access to a shared diagnostic does not grant permission to change production infrastructure.

Policies default to deny; deny overrides approval, which overrides allow. Manager approval uses the requester's actual directory manager. Scenario configuration cannot change these rules.

## Evaluation

`tests/conversations/expected_outcomes.json` selects two example employees for each of seven problem types: 14 independent live trials. These are test actors, not template restrictions. Several actors appear in multiple problem types. `scripts/run_evaluation.py --list` previews the matrix without model calls; `--scenarios` and `--employees` filter it. Expectations remain outside agent context.

Offline tests cover reusable injection across all eight employees, reproducible overlapping conditions, personal repair isolation, shared-resource authorization, regional effects and department/manager-dependent access decisions. A successful data or offline test does not establish live model quality on the new matrix.
