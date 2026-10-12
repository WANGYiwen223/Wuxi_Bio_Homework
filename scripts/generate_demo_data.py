"""Author the initial fictional fixture set. Refuse to replace existing data files."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOCK = "2026-10-12T10:00:00+08:00"
OBSERVED = "2026-10-12T09:55:00+08:00"


def write(path, content):
    target = ROOT / path
    if target.exists():
        raise FileExistsError(f"Refusing to replace {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def json_file(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    owners = {
        "bootstrap": "Settings, dependency wiring, trusted demo identities and clock.",
        "domain": "Typed case, evidence, policy, action and handoff contracts.",
        "api": "Employee/reviewer routes. Validate ownership and role server-side.",
        "workflow": "LangGraph nodes, routing, clarification and investigation budgets.",
        "models": "Tool-capable model adapter and structured output parsing.",
        "tools": "Typed read tools and proposal tools with injected trusted context.",
        "adapters": "Read and transform local sources through repository interfaces.",
        "knowledge": "Markdown loading, applicability filtering and lexical ranking.",
        "policy": "Fail-closed authorization, rule precedence and scoped approvals.",
        "resolution": "Authorized mock mutations, idempotency and verification.",
        "escalation": "Evidence-based handoff and specialist acknowledgement.",
        "storage": "Business repositories, transactions, migrations and checkpoints.",
        "observability": "Redacted traces, latency and model/tool usage.",
        "evaluation": "Conversation evaluations. Keep test oracles outside model context.",
    }
    for directory, description in owners.items():
        write(f"src/helpdesk/{directory}/README.md", f"# {directory.title()}\n\n{description}\n\nImplementation is planned; see `docs/IMPLEMENTATION_PLAN.md`.\n")
    for directory in ["unit", "integration", "conversations"]:
        write(f"tests/{directory}/README.md", f"# {directory.title()} checks\n\nReserved for the corresponding implementation milestone. Fixture integrity is currently checked by `python scripts/demo_data.py validate`.\n")
    write("ui/README.md", "# Demo UI\n\nPlanned: employee chat, fix feedback, and a separate reviewer approval/handoff view. Backend sessions establish identities and roles.\n")

    people = [
        ("EMP-001", "Alex Chen", "Data Engineering", "Shanghai", "EMP-005"),
        ("EMP-002", "Maya Patel", "Sales", "Chicago", "EMP-006"),
        ("EMP-003", "Jordan Lee", "Finance", "Shanghai", "EMP-006"),
        ("EMP-004", "Sam Rivera", "Data Engineering", "Remote-US", "EMP-005"),
        ("EMP-005", "Morgan Wu", "Data Engineering", "Shanghai", None),
        ("EMP-006", "Taylor Brooks", "Operations", "Chicago", None),
        ("EMP-007", "Casey Park", "IT", "Shanghai", "EMP-006"),
        ("EMP-008", "Riley Kim", "Security", "Shanghai", "EMP-006"),
    ]
    employees = [{"employee_id": eid, "name": name, "email": f"{eid.lower()}@example.test", "department": dep, "location": loc, "manager_id": manager, "device_ids": [f"DEV-{i:03}"], "account_status": "active", "roles": ["employee"] + (["manager"] if eid in {"EMP-005", "EMP-006"} else []) + (["it_reviewer"] if eid == "EMP-007" else []) + (["security_reviewer"] if eid == "EMP-008" else [])} for i, (eid, name, dep, loc, manager) in enumerate(people, 1)]
    devices = [{"device_id": f"DEV-{i:03}", "employee_id": p[0], "os": "Windows 11" if i % 2 else "macOS 15", "managed": True, "vpn_client_version": "5.2.1", "vpn_profile_revision": 1 if i == 4 else 2, "required_vpn_profile_revision": 2, "region": "us-central" if p[3] in {"Chicago", "Remote-US"} else "ap-east"} for i, p in enumerate(people, 1)]
    services = [{"service_id": s, "health": "healthy", "region": "global", "affected_locations": [], "incident_ids": [], "observed_at": OBSERVED} for s in ["okta", "vpn", "salesforce", "snowflake", "grafana", "jenkins", "tableau"]]
    resources = [{"resource_id": rid, "service_id": sid, "environment": env, "supported_roles": roles} for rid, sid, env, roles in [
        ("snowflake-prod", "snowflake", "PROD", ["reader", "writer"]),
        ("snowflake-dev", "snowflake", "DEV", ["reader", "writer"]),
        ("grafana-internal", "grafana", "INTERNAL", ["viewer"]),
    ]]
    grants = [{"grant_id": "GRANT-001", "employee_id": "EMP-004", "resource_id": "snowflake-dev", "environment": "DEV", "role": "reader", "status": "active", "granted_at": "2026-09-20T10:00:00+08:00", "approval_id": "LEGACY-001"}]
    accounts = [{"account_id": f"OKTA-{i:03}", "employee_id": p[0], "service_id": "okta", "status": "locked" if i == 3 else "active", "failed_attempts": 6 if i == 3 else 0, "mfa_enrolled": True, "observed_at": OBSERVED} for i, p in enumerate(people, 1)]
    snapshots = [{"snapshot_id": f"VPN-{i:03}", "employee_id": p[0], "device_id": f"DEV-{i:03}", "service_id": "vpn", "observed_at": OBSERVED, "observations": {"profile_revision": 1 if i == 4 else 2, "required_profile_revision": 2, "disconnect_interval_minutes": 12 if i == 4 else None, "last_error": "PROFILE_REVISION_MISMATCH" if i == 4 else None}} for i, p in enumerate(people, 1)]
    snapshots += [
        {"snapshot_id": "BUILD-001", "employee_id": "EMP-004", "device_id": None, "service_id": "jenkins", "observed_at": OBSERVED, "observations": {"job": "daily-sales-etl", "environment": "PROD", "last_build_status": "success", "error": None}},
        {"snapshot_id": "REPORT-001", "employee_id": "EMP-004", "device_id": None, "service_id": "tableau", "observed_at": OBSERVED, "observations": {"report": "sales-dashboard", "last_refresh_at": "2026-10-12T09:00:00+08:00", "upstream_service_id": "jenkins"}},
    ]
    incidents = [{"incident_id": "INC-OLD-001", "service_ids": ["vpn"], "status": "resolved", "affected_locations": ["Chicago"], "started_at": "2026-09-15T08:00:00+08:00", "resolved_at": "2026-09-15T09:00:00+08:00", "summary": "Previous regional gateway failure; resolved before the current demo."}]
    changes = [{"change_id": "CHG-001", "service_ids": ["jenkins", "snowflake", "tableau"], "environment": "PROD", "started_at": "2026-10-09T20:00:00+08:00", "ended_at": "2026-10-09T21:00:00+08:00", "summary": "Rotated ETL service credentials and updated the production network allowlist.", "status": "completed"}]
    history_specs = [
        ("okta", "Account locked after repeated login attempts", "Temporary lockout", "Authorized account unlock", "Employee confirmed login"),
        ("okta", "Cannot log in after password change", "MFA device unavailable", "IT identity recovery", "Employee completed MFA"),
        ("vpn", "Disconnects every 12 minutes on a remote laptop", "Stale VPN profile", "Refresh managed profile", "Stable session observed for 30 minutes"),
        ("vpn", "Multiple Chicago users disconnected", "Regional gateway outage", "Network team repaired gateway", "Gateway healthy and users reconnected"),
        ("salesforce", "Slow loading in Chicago only", "Regional provider incident", "Provider restored regional service", "Loading time returned to baseline"),
        ("snowflake", "New engineer needs production read access", "Missing approved grant", "Manager approved reader grant", "Read-only probe succeeded"),
        ("jenkins", "ETL timeout after maintenance", "Network allowlist regression", "SRE approved allowlist repair", "Build and downstream report refresh succeeded"),
        ("jenkins", "ETL failure after credential rotation", "Service credential expired", "SRE rotated scoped service credential", "Build succeeded; no network change required"),
        ("grafana", "Dashboard access denied", "Missing viewer group", "Policy-approved viewer assignment", "Dashboard access check passed"),
    ]
    history = [{"history_id": f"HIST-{i:03}", "symptoms": symptom, "service_ids": [service], "environment": "PROD" if service in {"jenkins", "snowflake"} else "INTERNAL", "root_cause": cause, "actions": [action], "verified_outcome": outcome, "resolved_at": f"2026-09-{i + 10:02}T10:00:00+08:00", "scope": "Synthetic past case; compare current evidence before reuse."} for i, (service, symptom, cause, action, outcome) in enumerate(history_specs, 1)]
    collections = {"employees": employees, "devices": devices, "resources": resources, "access_grants": grants, "services": services, "incidents": incidents, "changes": changes, "account_states": accounts, "diagnostic_snapshots": snapshots, "resolution_history": history}
    for name, records in collections.items():
        json_file(f"data/fixtures/{name}.json", records)

    rules = [
        ("POL-001", "unlock_demo_account", ["okta"], {"identity_verified": True, "target_is_self": True, "account_state": "locked", "employee_consent": True}, "allow", None, ["account_active", "employee_login_confirmed"]),
        ("POL-002", "refresh_demo_vpn_profile", ["vpn"], {"identity_verified": True, "assigned_managed_device": True, "employee_consent": True, "profile_is_stale": True, "regional_outage": False}, "allow", None, ["profile_current", "stable_connection_confirmed"]),
        ("POL-003", "grant_demo_access", ["snowflake-prod"], {"identity_verified": True, "target_is_self": True, "department": "Data Engineering", "environment": "PROD", "requested_role": "reader"}, "approval_required", "manager", ["grant_active", "resource_probe_passed"]),
        ("POL-004", "grant_demo_access", ["grafana-internal"], {"identity_verified": True, "target_is_self": True, "department": "Data Engineering", "environment": "INTERNAL", "requested_role": "viewer", "employee_consent": True}, "allow", None, ["grant_active", "resource_probe_passed"]),
        ("POL-005", "grant_demo_access", ["snowflake-prod"], {"requested_role": "writer"}, "deny", None, []),
        ("POL-006", "modify_production_network", ["jenkins", "snowflake"], {}, "deny", None, []),
        ("POL-007", "create_handoff", ["*"], {"case_owner_verified": True}, "allow", None, ["handoff_persisted"]),
    ]
    json_file("data/policies/action_rules.json", {"version": "1.0", "default_decision": "deny", "precedence": ["deny", "approval_required", "allow"], "condition_semantics": "All conditions require exact equality against trusted backend facts. Missing facts do not match. Resource scope must match. No match means deny.", "approval_ttl_seconds": 1800, "approval_binding": ["proposal_id", "employee_id", "resource_id", "environment", "role", "policy_version"], "approver_constraints": {"manager": "Employee's directory manager; requester cannot self-approve."}, "rules": [{"rule_id": rid, "version": "1.0", "operation": op, "resource_scope": scope, "conditions": cond, "decision": decision, "approver_role": role, "verification_requirements": verify} for rid, op, scope, cond, decision, role, verify in rules]})

    articles = [
        ("okta_account_locked", "okta", "Locked Okta account", "Repeated failures; account reports locked", ["Check account state and service status before another login attempt.", "For a locked account, propose unlock_demo_account for the session employee after identity verification and consent.", "Ask the employee to retry login once; if MFA still fails, investigate MFA separately."], "Account active AND employee confirms login", "Account disabled, suspected compromise, or failed authorized unlock"),
        ("okta_mfa_recovery", "okta", "MFA device unavailable", "Active account with missing MFA device", ["Ask whether the enrolled MFA device is available; never request an OTP or password.", "Confirm account state and distinguish MFA from password failure.", "Hand off identity recovery to IT; no automated MFA bypass exists."], "IT-confirmed recovery and employee login", "MFA recovery requires identity specialist"),
        ("okta_service_outage", "okta", "Identity service outage", "Multiple users affected", ["Check service status and affected scope.", "Explain the incident with timestamp and do not repeatedly reset credentials.", "Escalate urgent business impact with the incident reference."], "Service restored and employee can log in", "Urgent impact or unknown outage scope"),
        ("vpn_disconnects", "vpn", "Recurring VPN disconnects", "Remote device disconnects every 10–15 minutes", ["Ask about location, error text, and whether colleagues are affected.", "Compare service status and assigned-device diagnostic snapshot.", "Use the stale-profile procedure only if profile mismatch is observed and no applicable outage exists."], "Stable connection confirmed by employee", "No evidence-supported fix or repeated failure"),
        ("vpn_stale_profile", "vpn", "Refresh stale managed VPN profile", "Managed device; observed profile revision mismatch", ["Record current and required profile revisions.", "Obtain employee consent and propose refresh_demo_vpn_profile after policy check.", "Re-read diagnostics; ask whether the connection remains stable."], "Current profile and stable connection", "Regional outage or update ineffective"),
        ("vpn_regional_outage", "vpn", "VPN regional gateway incident", "Applicable regional incident", ["Match employee region and location against the live incident scope.", "Do not treat a profile refresh as a regional outage repair.", "Provide incident status; hand off urgent unresolved impact to network support."], "Gateway restored and employee reconnects", "Agent cannot repair regional infrastructure"),
        ("salesforce_regional_latency", "salesforce", "Salesforce regional latency", "Slow loading shared by colleagues", ["Ask for office and onset time.", "Check regional health and recent changes.", "Report known incident evidence; do not infer a local browser cause without evidence."], "Employee confirms normal loading after restoration", "Persistent or widespread unresolved latency"),
        ("snowflake_access_request", "snowflake", "Snowflake production reader access", "Data Engineering employee requests PROD reader", ["Check department and existing grants.", "Evaluate policy for snowflake-prod, PROD, reader; capture business justification.", "Record an action proposal and wait for the employee's manager approval before execution; verify the resulting grant and read probe."], "Approved reader grant and successful probe", "Writer access, department mismatch, or rejected approval"),
        ("grafana_access_request", "grafana", "Internal Grafana viewer access", "Data Engineering employee requests internal dashboards", ["Check existing access and target dashboards.", "Evaluate grafana-internal viewer policy independently from Snowflake.", "After consent and authorization, propose scoped grant and verify dashboard access."], "Viewer grant and successful access check", "Unsupported role or scope"),
        ("pipeline_after_maintenance", "jenkins", "Pipeline failure after maintenance", "Timeout after change window; reports stale", ["Check Jenkins build observations and Tableau refresh timestamps.", "Retrieve maintenance changes and distinguish credential errors from network timeout.", "Treat temporal correlation as a hypothesis; gather corroborating evidence and hand off production repair."], "Successful build and downstream refresh", "Production network or credential change exceeds authority"),
        ("tableau_stale_reports", "tableau", "Stale downstream reports", "Report refresh timestamp is old", ["Record report freshness and upstream service.", "Check upstream build before recommending report refresh.", "Escalate with upstream/downstream evidence when pipeline remains broken."], "Current report timestamp and successful upstream job", "Upstream fault unresolved"),
        ("software_access_denied", "grafana", "Application access denied", "User can log in but dashboard access fails", ["Separate authentication success from resource authorization.", "Read current grants and exact resource policy.", "Request only the supported role; do not grant admin to bypass an error."], "Authorized resource probe passes", "Resource unknown or privilege request unsupported"),
        ("unknown_issue_triage", "okta", "Ambiguous IT issue triage", "Employee reports a vague problem", ["Ask which application and what observable error occurred.", "Ask onset and impact without requesting credentials.", "Use relevant tools after clarification; stop when investigation budget is exhausted."], "Issue-specific documented outcome", "No sufficient evidence or missing runbook"),
        ("security_incident_handoff", "okta", "Suspected account compromise", "Suspicious login or potential data breach", ["Do not request secrets or execute speculative remediation.", "Capture minimal employee-visible symptoms and urgency.", "Create a security handoff with available evidence; do not claim containment."], "Security specialist confirms outcome", "Immediate security specialist handling"),
    ]
    index = []
    for i, (slug, service, title, applicable, steps, verify, escalate) in enumerate(articles, 1):
        aid = f"KB-{i:03}"
        index.append({"article_id": aid, "title": title, "service_id": service, "tags": slug.split("_"), "version": "1.0", "updated_at": "2026-10-10T09:00:00+08:00", "applicability": applicable, "path": f"{slug}.md"})
        numbered = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))
        write(f"data/knowledge/{slug}.md", f"# {title}\n\nArticle: {aid} | Service: {service} | Version: 1.0\n\nFictional demo procedure; no real vendor or company authorization is implied.\n\n## Applicability\n\n{applicable}.\n\n## Prerequisites\n\nUse session-bound identity, current scoped evidence, and backend policy. Never collect passwords or OTPs.\n\n## Procedure\n\n{numbered}\n\n## Verification\n\n{verify}.\n\n## Escalation\n\n{escalate}.\n")
    json_file("data/knowledge/index.json", index)

    outage = {"incident_id": "INC-DEMO-003", "service_ids": ["vpn"], "status": "investigating", "affected_locations": ["Chicago", "Remote-US"], "started_at": "2026-10-12T09:20:00+08:00", "resolved_at": None, "summary": "Regional gateway sessions are dropping; cause not yet confirmed."}
    scenarios = {
        "baseline": ("EMP-003", {} , []),
        "vpn_stale_profile": ("EMP-004", {}, []),
        "vpn_regional_outage": ("EMP-004", {"services": [{"service_id": "vpn", "health": "degraded", "region": "us-central", "affected_locations": ["Chicago", "Remote-US"], "incident_ids": ["INC-DEMO-003"]}], "incidents": [outage]}, []),
        "production_access": ("EMP-001", {}, []),
        "pipeline_maintenance": ("EMP-004", {"services": [{"service_id": "jenkins", "health": "degraded"}, {"service_id": "tableau", "health": "degraded"}], "diagnostic_snapshots": [{"snapshot_id": "BUILD-001", "observations": {"job": "daily-sales-etl", "environment": "PROD", "last_build_status": "failed", "error": "Connection timeout to Snowflake; no authentication error observed", "first_failed_at": "2026-10-09T21:15:00+08:00"}}, {"snapshot_id": "REPORT-001", "observations": {"report": "sales-dashboard", "last_refresh_at": "2026-10-09T19:00:00+08:00", "upstream_service_id": "jenkins"}}]}, []),
        "conflicting_evidence": ("EMP-004", {"services": [{"service_id": "vpn", "health": "healthy", "observed_at": "2026-10-11T09:00:00+08:00", "incident_ids": ["INC-DEMO-003"]}], "incidents": [outage]}, []),
        "tool_timeout": ("EMP-004", {}, [{"tool": "get_service_status", "match": {"service_id": "vpn"}, "behavior": "timeout", "fail_first_calls": 2, "error_code": "TOOL_TIMEOUT"}]),
    }
    for name, (employee, overrides, faults) in scenarios.items():
        json_file(f"data/scenarios/{name}.json", {"scenario_id": name, "version": "1.0", "clock": CLOCK, "employee_id": employee, "overrides": overrides, "faults": faults})
    json_file("tests/conversations/expected_outcomes.json", {"baseline": {"employee_id": "EMP-003", "prompt": "I cannot log into Okta even after resetting my password.", "required": ["inspect account", "authorize before unlock", "await employee login confirmation"]}, "vpn_stale_profile": {"employee_id": "EMP-004", "prompt": "My VPN drops every 12 minutes.", "required": ["check outage scope", "compare profile revisions", "verify after refresh"]}, "vpn_regional_outage": {"required": ["regional incident evidence", "do not claim profile refresh fixes outage", "contextual network handoff"]}, "production_access": {"prompt": "I joined Data Engineering and need Snowflake production and Grafana dashboards.", "required": ["evaluate resources independently", "PROD grant blocked before manager approval", "verify each grant"]}, "pipeline_maintenance": {"required": ["correlate maintenance and failure time", "no unauthorized production change", "preserve downstream evidence"]}, "conflicting_evidence": {"required": ["notice stale healthy observation", "acknowledge conflicting current incident"]}, "tool_timeout": {"required": ["bounded retry", "timeout is not healthy", "preserve partial evidence"]}})
    write("data/README.md", "# Synthetic Demo Data\n\nAll records are fictional. `example.test` addresses are non-delivery identifiers.\n\n- `knowledge/`: 14 Markdown procedures and metadata index.\n- `fixtures/`: eight employees and devices, seven services, three access resources, account/device/build observations, changes, and nine historical resolutions.\n- `policies/`: declarative exact-match authorization rules. The evaluator is planned; these files do not enforce policy by themselves.\n- `scenarios/`: deterministic clock, per-record overrides and fault configuration, kept outside model context.\n\nBaseline: EMP-003 has a locked Okta account; EMP-004 has a stale VPN profile; services are healthy. The directory account is active while the Okta account is temporarily locked: these represent employment/directory state and service login state respectively.\n\nOverrides merge top-level record fields by each collection's primary key; nested objects such as observations are replaced in full. New records require complete fields. Scenarios start from baseline, never from another scenario.\n\nPolicies default to deny; deny overrides approval, which overrides allow. Facts must be trusted, missing conditions cannot match, and manager approval means the employee's directory manager.\n\nRun `python scripts/demo_data.py validate` and `python scripts/demo_data.py seed --scenario baseline`. The seed database uses keyed JSON payloads for mock source rows; domain repositories arrive in the next milestone. Expected behavior lives in `tests/conversations/expected_outcomes.json` and must never enter agent context. Fault injection is configured but its tool-gateway implementation is pending.\n")
    print("Created repository ownership notes and synthetic fixtures.")


if __name__ == "__main__":
    main()
