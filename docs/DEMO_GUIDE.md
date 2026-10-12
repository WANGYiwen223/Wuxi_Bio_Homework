# Interview Demo Guide

Run setup commands from README. Explain that the model is real, the IT systems are synthetic, and identity selection simulates SSO locally.

| Scenario | Employee | Opening issue | Observe |
|---|---|---|---|
| `baseline` | EMP-003 | Cannot log into Okta after password reset; MFA is available. | Account-state query, documented unlock, explicit consent, simulated mutation, employee verification. |
| `vpn_stale_profile` | EMP-004 | VPN disconnects every 12 minutes on the assigned remote laptop. | Status scope and device/profile evidence; refresh only after consent; verify stable connection. |
| `vpn_regional_outage` | EMP-004 | Remote VPN and Chicago colleagues disconnect repeatedly. | Incident scope; no local profile fix claimed as outage repair; network handoff. |
| `production_access` | EMP-001 | Need Snowflake PROD reader and internal Grafana viewer access for reporting. | Both resources recorded separately; manager EMP-005 reviews PROD; grants verified; no partial-case closure. |
| `pipeline_maintenance` | EMP-004 | Jenkins daily-sales-etl times out since last Friday and Tableau sales-dashboard is stale. | Change window, build and report evidence; probable cause remains a hypothesis; SRE handoff. |
| `conflicting_evidence` | EMP-004 | VPN fails for me and Chicago colleagues; is the status current? | Stale healthy status conflicts with newer incident; preserve uncertainty and source times. |
| `tool_timeout` | EMP-004 | VPN drops every 12 minutes with profile mismatch. | First two status calls fail; bounded recovery or useful handoff with errors retained. |

Create a fresh directory for each scenario using `scripts/demo_data.py seed --scenario <name> --run-id <unique-id>`. Set `HELPDESK_RUN_DIR` and restart the local server. Do not modify seed JSON to make a failed demo pass.

Demonstrate a fresh unplanned problem as well. Show clarifying questions and explain that prompts select tools while ordinary code enforces identity, authorization, budgets, transactions and lifecycle transitions.

For human review, select the fixture reviewer in the separate panel. Managers see assigned approvals; IT/security specialists see their permitted handoff group. Acknowledging a handoff does not mark an employee's problem solved.

Tradeoffs: lexical retrieval suits the small corpus; fixed demo time makes tests repeatable; a single local worker serializes conversational turns; real SSO, IT APIs, streaming, retention policies and distributed workers are future production work. Backend and checkpoint stores have separate transactions, so proposals/actions use durable idempotency and interrupted dialogue is reconciled without replaying side effects.
