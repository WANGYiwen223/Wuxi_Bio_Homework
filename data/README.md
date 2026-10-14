# Synthetic Demo Data / 合成数据

All records are fictional. `example.test` addresses are non-delivery identifiers.

员工身份、问题条件、评测用例分别建模：同类问题可发生在不同员工身上，同一员工可同时遇到账号、设备、权限或共享系统问题。员工编号不决定问题类型。

## Five source categories

| Source | Files | Scope |
|---|---|---|
| Knowledge base | `knowledge/`: 14 indexed Markdown articles, FAQs and runbooks | Reusable procedures selected by symptoms and applicability, never employee ID |
| System status | `fixtures/services.json`, `incidents.json`, `changes.json`, shared `diagnostic_snapshots.json` | Seven services; incidents scoped by location; changes and build/report observations scoped by service/resource |
| User directory | `fixtures/employees.json`, `devices.json`, `account_states.json`, `resources.json`, `access_grants.json` | Eight employees with departments, roles, locations, managers, equipment and permissions; private account/device state stays owned by its employee |
| Resolution history | `fixtures/resolution_history.json` | Nine searchable past resolutions; they do not prescribe a current answer |
| Policy / rules | `policies/action_rules.json`; shared-resource `diagnostic_readers` scopes | Seven action rules distinguish allowed operations, manager approval and denial |

The resources include three access-grant targets and two shared diagnostic targets. Account/device diagnostics complement directory and system observations.

## Healthy baseline and reusable conditions

`scripts/generate_demo_data.py` generates healthy fixture records (active accounts, current VPN profiles, successful builds/reports); knowledge, policy, and scenario files are curated and never overwritten by it.

```powershell
.\.venv\Scripts\python.exe scripts/generate_demo_data.py --overwrite
.\.venv\Scripts\python.exe scripts/demo_data.py validate
```

`scenarios/` contains environment templates with a fixed clock, personal `conditions`, shared-record `overrides`, and tool `faults`; there is no scenario-level `employee_id`:

- `baseline`: healthy control environment.
- `account_lockout` / `vpn_stale_profile`: inject the personal condition into the selected employees.
- `production_access`: healthy systems; policies decide each request using the actual employee's department and manager.
- `vpn_regional_outage` / `conflicting_evidence`: a shared Chicago/Remote-US VPN incident with fresh or conflicting status evidence; location determines whether it applies.
- `pipeline_maintenance`: shared Jenkins build failure and stale Tableau report after a change window.
- `tool_timeout`: stale profiles plus bounded simulated status-tool timeouts.
- `mixed_issues` (default): overlapping locked accounts (4 employees) and stale profiles (5), plus a shared pipeline incident; application access can be requested independently.

Without `--employees`, personal conditions consider all eligible active employees; an optional `count` samples from that pool using `--random-seed` (default 42). Each selected employee's managed devices and matching observations are updated together. Shared incidents retain their scope regardless of `--employees`.

```powershell
# Default mixed environment, reproducible sampling.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --run-id mixed-demo --random-seed 42
# The SAME fault applied to chosen employees without editing source JSON.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --scenario account_lockout --employees EMP-001,EMP-002 --run-id account-demo
# The SAME employees with both personal faults plus the shared pipeline issue.
.\.venv\Scripts\python.exe scripts/demo_data.py seed --scenario mixed_issues --employees EMP-001,EMP-004 --run-id combined-demo
```

Seeding prints personal fault assignments; the operator-only `manifest.json` records seed and assignments but does not choose a login identity. Runtime tools read factual state from SQLite, not scenario labels or evaluation expectations. `ReadTools` implements configured timeouts with persisted per-case counters.

Every scenario starts from healthy fixtures: shared overrides merge top-level fields by primary key (nested observations are replaced in full), personal conditions are then materialized, and all references are validated. Existing run databases are never overwritten — to use new data, seed a fresh run, set `HELPDESK_RUN_DIR=var/runs/<run-id>`, and restart the server.

## Shared resources and identity boundaries

Private accounts and devices remain employee-owned. Jenkins `jenkins-sales-etl` and Tableau `tableau-sales-dashboard` observations are shared (`employee_id: null`, `resource_id` set); Data Engineering employees and the IT reviewer can inspect them per resource `diagnostic_readers`, rechecked on every read. Authorized readers see identical facts while evidence and cases remain separately owned. Shared diagnostic access never permits production repair.

`get_employee_context` returns roles and authorized diagnostic resources alongside personal state. `get_diagnostic_snapshot` accepts an optional `device_id` or `resource_id` (mutually exclusive). Policies default to deny; deny overrides approval, which overrides allow. Manager approval uses the requester's actual directory manager and cannot be changed by scenario configuration.

## Evaluation

`tests/conversations/expected_outcomes.json` selects two example employees for each of seven problem types: 14 independent live trials. These are test actors, not template restrictions. `scripts/run_evaluation.py --list` previews the matrix without model calls; `--scenarios` and `--employees` filter it. Expectations remain outside agent context.

Offline tests cover reusable injection across all eight employees, reproducible overlapping conditions, personal repair isolation, shared-resource authorization, regional effects, and department/manager-dependent access decisions. A successful offline test does not establish live model quality on the new matrix.
