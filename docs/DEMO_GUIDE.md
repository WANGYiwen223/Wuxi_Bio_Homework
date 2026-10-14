# Interview Demo Guide

The model is real; all IT systems and employees are synthetic. Identity selection simulates SSO locally, and employees are not assigned a single problem type.

Seed with `scripts/demo_data.py seed --scenario mixed_issues --run-id <unique-id> --random-seed 42`, set `HELPDESK_RUN_DIR` to that run, and restart the server. The seed output and operator manifest list who has a locked account or stale VPN profile; the same employee may have both, and shared incidents and access requests are additional independent problems. Create separate cases for separate issues so a resolved case is not reused. For a targeted example, use `--employees EMP-001,EMP-004`; changing the random seed changes the personal fault distribution while preserving identities.

| Scenario | Employee selection | Opening issue | Observe |
|---|---|---|---|
| `baseline` | Any active employee | Ask to check account/device status | Healthy control data; no invented lockout or stale profile |
| `account_lockout` | Any employee included in injection | Cannot log into Okta after password reset; MFA is available. | Read actual account state, consent, authorized unlock, verification |
| `vpn_stale_profile` | Any injected employee with a managed device | VPN disconnects every 12 minutes; profile revision mismatch. | Check personal device and service scope; refresh and verify |
| `vpn_regional_outage` | Chicago/Remote-US employee, then compare Shanghai | VPN and Chicago colleagues disconnect repeatedly. | Geographic scope decides whether a local refresh is allowed; a shared outage is not repaired by refreshing a device |
| `production_access` | Data Engineering employees; compare a Sales employee | Need Snowflake PROD reader and internal Grafana viewer access. | Independent resource checks; actual directory manager approval; department mismatch denied |
| `pipeline_maintenance` | Any Data Engineering employee or IT reviewer | Jenkins daily-sales-etl times out since Friday; Tableau sales-dashboard is stale. | Authorized readers see the same shared evidence; SRE handoff, no production mutation |
| `conflicting_evidence` | An employee in the incident's affected locations | VPN fails for me and Chicago colleagues; is the status current? | Stale healthy status conflicts with a newer incident; uncertainty preserved |
| `tool_timeout` | Any injected employee | VPN drops every 12 minutes with profile mismatch. | First two status calls fail; bounded recovery or useful handoff |

Switch scenarios by creating a fresh run; never modify an existing database or seed JSON just to make a failed demo pass. New source files do not migrate old runs automatically.

Managers see assigned approvals; IT/security specialists see their permitted handoff groups in the separate review panel. Acknowledgement does not mark an employee's problem solved, and shared diagnostic read access does not permit production repair.

Demonstrate an unplanned issue as well: prompts choose tools, while ordinary code enforces identity, authorization, budgets, transactions, and lifecycle transitions. Reproducible synthetic samples are not a claim about real-world incident frequency or model reliability.
