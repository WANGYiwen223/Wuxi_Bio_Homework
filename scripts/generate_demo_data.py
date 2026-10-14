"""Generate healthy fictional source records; scenarios inject problems separately.

Knowledge articles, policy rules and scenario templates are curated files, not
rewritten by this generator. Use --overwrite to refresh only generated fixtures.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = "2026-10-12T09:55:00+08:00"


def build_fixtures():
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
    devices = [{"device_id": f"DEV-{i:03}", "employee_id": p[0], "os": "Windows 11" if i % 2 else "macOS 15", "managed": True, "vpn_client_version": "5.2.1", "vpn_profile_revision": 2, "required_vpn_profile_revision": 2, "region": "us-central" if p[3] in {"Chicago", "Remote-US"} else "ap-east"} for i, p in enumerate(people, 1)]
    services = [{"service_id": s, "health": "healthy", "region": "global", "affected_locations": [], "incident_ids": [], "observed_at": OBSERVED} for s in ["okta", "vpn", "salesforce", "snowflake", "grafana", "jenkins", "tableau"]]
    resources = [{"resource_id": rid, "service_id": sid, "environment": env, "supported_roles": roles} for rid, sid, env, roles in [
        ("snowflake-prod", "snowflake", "PROD", ["reader", "writer"]),
        ("snowflake-dev", "snowflake", "DEV", ["reader", "writer"]),
        ("grafana-internal", "grafana", "INTERNAL", ["viewer"]),
    ]]
    resources += [
        {"resource_id": rid, "service_id": sid, "environment": "PROD", "supported_roles": ["viewer"],
         "diagnostic_readers": {"departments": ["Data Engineering"], "roles": ["it_reviewer"]}}
        for rid, sid in [("jenkins-sales-etl", "jenkins"), ("tableau-sales-dashboard", "tableau")]
    ]
    grants = [{"grant_id": "GRANT-001", "employee_id": "EMP-004", "resource_id": "snowflake-dev", "environment": "DEV", "role": "reader", "status": "active", "granted_at": "2026-09-20T10:00:00+08:00", "approval_id": "LEGACY-001"}]
    accounts = [{"account_id": f"OKTA-{i:03}", "employee_id": p[0], "service_id": "okta", "status": "active", "failed_attempts": 0, "mfa_enrolled": True, "observed_at": OBSERVED} for i, p in enumerate(people, 1)]
    snapshots = [{"snapshot_id": f"VPN-{i:03}", "employee_id": p[0], "device_id": f"DEV-{i:03}", "service_id": "vpn", "observed_at": OBSERVED, "observations": {"profile_revision": 2, "required_profile_revision": 2, "disconnect_interval_minutes": None, "last_error": None}} for i, p in enumerate(people, 1)]
    snapshots += [
        {"snapshot_id": "BUILD-001", "employee_id": None, "resource_id": "jenkins-sales-etl", "device_id": None, "service_id": "jenkins", "observed_at": OBSERVED, "observations": {"job": "daily-sales-etl", "environment": "PROD", "last_build_status": "success", "error": None}},
        {"snapshot_id": "REPORT-001", "employee_id": None, "resource_id": "tableau-sales-dashboard", "device_id": None, "service_id": "tableau", "observed_at": OBSERVED, "observations": {"report": "sales-dashboard", "last_refresh_at": "2026-10-12T09:00:00+08:00", "upstream_service_id": "jenkins"}},
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
    return collections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/fixtures")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    records = build_fixtures()
    paths = {name: args.output_dir / f"{name}.json" for name in records}
    if not args.overwrite and any(path.exists() for path in paths.values()):
        parser.error("Fixtures already exist; choose a new --output-dir or use --overwrite")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in records.items():
        paths[name].write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {sum(map(len, records.values()))} healthy source records in {args.output_dir}")


if __name__ == "__main__":
    main()
