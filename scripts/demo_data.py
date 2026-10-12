"""Validate fictional sources and seed isolated local SQLite demo databases."""

import argparse
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
COLLECTIONS = {
    "employees": ("employee_id", {"name", "department", "location", "manager_id", "device_ids", "account_status", "roles"}),
    "devices": ("device_id", {"employee_id", "managed", "vpn_profile_revision", "required_vpn_profile_revision", "region"}),
    "resources": ("resource_id", {"service_id", "environment", "supported_roles"}),
    "access_grants": ("grant_id", {"employee_id", "resource_id", "environment", "role", "status", "granted_at", "approval_id"}),
    "services": ("service_id", {"health", "region", "affected_locations", "incident_ids", "observed_at"}),
    "incidents": ("incident_id", {"service_ids", "status", "started_at", "resolved_at", "summary", "affected_locations"}),
    "changes": ("change_id", {"service_ids", "environment", "started_at", "ended_at", "summary", "status"}),
    "account_states": ("account_id", {"employee_id", "service_id", "status", "mfa_enrolled", "observed_at"}),
    "diagnostic_snapshots": ("snapshot_id", {"employee_id", "device_id", "service_id", "observed_at", "observations"}),
    "resolution_history": ("history_id", {"symptoms", "service_ids", "environment", "root_cause", "actions", "verified_outcome", "resolved_at"}),
}
OPERATIONS = {"unlock_demo_account", "refresh_demo_vpn_profile", "grant_demo_access", "modify_production_network", "create_handoff"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def aware_time(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, f"Timestamp needs timezone: {value}")
    return parsed


def check_timestamps(value, clock):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_at") and item is not None:
                require(aware_time(item) <= clock, f"Future observation: {key}={item}")
            else:
                check_timestamps(item, clock)
    elif isinstance(value, list):
        for item in value:
            check_timestamps(item, clock)


def load_scenario(name):
    require(re.fullmatch(r"[a-z0-9_-]+", name), "Invalid scenario name")
    scenario = read_json(DATA / "scenarios" / f"{name}.json")
    require(scenario["scenario_id"] == name, "Scenario filename/ID mismatch")
    records = {name: read_json(DATA / "fixtures" / f"{name}.json") for name in COLLECTIONS}
    for collection, patches in scenario["overrides"].items():
        require(collection in COLLECTIONS, f"Unknown override collection: {collection}")
        key = COLLECTIONS[collection][0]
        indexed = {row[key]: row for row in records[collection]}
        seen = set()
        for patch in patches:
            require(key in patch, f"Override needs {key}")
            identifier = patch[key]
            require(identifier not in seen, f"Duplicate override: {identifier}")
            seen.add(identifier)
            indexed[identifier] = {**indexed.get(identifier, {}), **patch}
        records[collection] = list(indexed.values())
    return scenario, records


def validate_scenario(scenario, records):
    clock = aware_time(scenario["clock"])
    indexes = {}
    for collection, (key, fields) in COLLECTIONS.items():
        rows = records[collection]
        require(isinstance(rows, list), f"{collection} must be an array")
        ids = []
        for row in rows:
            require(isinstance(row, dict), f"Invalid {collection} row")
            require({key, *fields} <= row.keys(), f"Missing {collection} fields: {({key, *fields} - row.keys())}")
            require(isinstance(row[key], str) and row[key], f"Invalid {collection} primary key")
            ids.append(row[key])
            check_timestamps(row, clock)
        require(len(ids) == len(set(ids)), f"Duplicate {collection} IDs")
        indexes[collection] = {row[key]: row for row in rows}

    def ref(collection, identifier):
        require(identifier in indexes[collection], f"Missing reference {collection}/{identifier}")
        return indexes[collection][identifier]

    ref("employees", scenario["employee_id"])
    for employee in records["employees"]:
        if employee["manager_id"]:
            manager = ref("employees", employee["manager_id"])
            require("manager" in manager["roles"], "Approver manager lacks manager role")
            require(employee["manager_id"] != employee["employee_id"], "Self-manager unsupported")
        for device_id in employee["device_ids"]:
            require(ref("devices", device_id)["employee_id"] == employee["employee_id"], "Employee/device ownership mismatch")
    for device in records["devices"]:
        require(device["device_id"] in ref("employees", device["employee_id"])["device_ids"], "Device missing from employee directory")
    for resource in records["resources"]:
        ref("services", resource["service_id"])
    for grant in records["access_grants"]:
        ref("employees", grant["employee_id"])
        resource = ref("resources", grant["resource_id"])
        require(grant["role"] in resource["supported_roles"] and grant["environment"] == resource["environment"], "Access grant scope mismatch")
    for service in records["services"]:
        require(service["health"] in {"healthy", "degraded", "outage", "unknown"}, "Invalid service health")
        for incident_id in service["incident_ids"]:
            require(service["service_id"] in ref("incidents", incident_id)["service_ids"], "Incident/service mismatch")
    for collection in ["incidents", "changes", "resolution_history"]:
        for row in records[collection]:
            for service_id in row["service_ids"]:
                ref("services", service_id)
            if collection == "incidents" and row["resolved_at"]:
                require(aware_time(row["started_at"]) <= aware_time(row["resolved_at"]), "Incident ends before start")
            if collection == "changes":
                require(aware_time(row["started_at"]) <= aware_time(row["ended_at"]), "Change ends before start")
    for collection in ["account_states", "diagnostic_snapshots"]:
        for row in records[collection]:
            ref("employees", row["employee_id"])
            ref("services", row["service_id"])
            if row.get("device_id"):
                device = ref("devices", row["device_id"])
                require(device["employee_id"] == row["employee_id"], "Diagnostic target ownership mismatch")
                if row["service_id"] == "vpn":
                    observations = row["observations"]
                    require(observations["profile_revision"] == device["vpn_profile_revision"], "Device/snapshot profile disagreement")
                    require(observations["required_profile_revision"] == device["required_vpn_profile_revision"], "Device/snapshot target profile disagreement")
    for fault in scenario["faults"]:
        require(fault["tool"] == "get_service_status" and fault["behavior"] == "timeout", "Unsupported fault definition")
        require(isinstance(fault["fail_first_calls"], int) and fault["fail_first_calls"] > 0, "Invalid fault count")
        ref("services", fault["match"]["service_id"])
    return indexes


def validate_common(indexes):
    articles = read_json(DATA / "knowledge/index.json")
    ids = set()
    base = (DATA / "knowledge").resolve()
    for article in articles:
        require({"article_id", "title", "service_id", "tags", "version", "updated_at", "applicability", "path"} <= article.keys(), "Missing KB metadata")
        require(article["article_id"] not in ids, "Duplicate article ID")
        ids.add(article["article_id"])
        require(article["service_id"] in indexes["services"], "Unknown KB service")
        path = (base / article["path"]).resolve()
        require(path.is_relative_to(base), "KB path escapes knowledge directory")
        text = path.read_text(encoding="utf-8")
        for heading in ["## Applicability", "## Prerequisites", "## Procedure", "## Verification", "## Escalation"]:
            require(heading in text, f"Missing {heading} in {path.name}")
        aware_time(article["updated_at"])
    policy = read_json(DATA / "policies/action_rules.json")
    require(policy["default_decision"] == "deny", "Policy must fail closed")
    require(policy["precedence"] == ["deny", "approval_required", "allow"], "Invalid policy precedence")
    rule_ids = set()
    scopes = {*indexes["services"], *indexes["resources"], "*"}
    for rule in policy["rules"]:
        require({"rule_id", "version", "operation", "resource_scope", "conditions", "decision", "approver_role", "verification_requirements"} <= rule.keys(), "Missing policy rule fields")
        require(rule["rule_id"] not in rule_ids, "Duplicate policy ID")
        rule_ids.add(rule["rule_id"])
        require(rule["operation"] in OPERATIONS and set(rule["resource_scope"]) <= scopes, "Unknown policy operation/scope")
        require(rule["decision"] in policy["precedence"], "Unknown policy decision")
        require(rule["decision"] != "approval_required" or rule["approver_role"], "Approval rule needs reviewer role")
    return len(articles), len(policy["rules"])


def validate_all():
    names = sorted(path.stem for path in (DATA / "scenarios").glob("*.json"))
    require(names, "No scenarios found")
    for name in names:
        scenario, records = load_scenario(name)
        indexes = validate_scenario(scenario, records)
        article_count, rule_count = validate_common(indexes)
    expected = read_json(ROOT / "tests/conversations/expected_outcomes.json")
    require(set(names) == set(expected), "Scenario/evaluation coverage mismatch")
    print(f"Validated {len(names)} scenarios, {article_count} articles, {rule_count} policy rules, and all fixture references.")
    return names


def seed(name, run_id=None):
    scenario, records = load_scenario(name)
    validate_common(validate_scenario(scenario, records))
    run_id = run_id or name
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", run_id), "Invalid run ID")
    run_dir = ROOT / "var/runs" / run_id
    db_path = run_dir / "helpdesk.sqlite"
    require(not db_path.exists(), f"Database exists: {db_path}. Choose a new --run-id.")
    run_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        for collection, rows in records.items():
            key = COLLECTIONS[collection][0]
            # Identifiers are fixed internal collection names, never user SQL input.
            db.execute(f"CREATE TABLE {collection} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.executemany(f"INSERT INTO {collection} VALUES (?, ?)", [(row[key], json.dumps(row)) for row in rows])
        for table in ["cases", "messages", "approvals", "actions", "evidence", "handoffs", "audit_events"]:
            db.execute(f"CREATE TABLE {table} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE runtime_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.executemany("INSERT INTO runtime_metadata VALUES (?, ?)", [("clock", scenario["clock"]), ("fixture_version", scenario["version"])])
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
        require(result == "ok", f"SQLite integrity failed: {result}")
        for collection, rows in records.items():
            require(db.execute(f"SELECT COUNT(*) FROM {collection}").fetchone()[0] == len(rows), f"Seed count mismatch: {collection}")
    # Kept outside the model-visible data repositories.
    manifest = {"scenario_id": name, "clock": scenario["clock"], "employee_id": scenario["employee_id"], "faults": scenario["faults"], "database": str(db_path), "counts": {name: len(rows) for name, rows in records.items()}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Seeded {name}: {sum(map(len, records.values()))} source records; SQLite integrity OK.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    seed_parser = commands.add_parser("seed")
    seed_parser.add_argument("--scenario", default="baseline")
    seed_parser.add_argument("--run-id")
    seed_parser.add_argument("--all", action="store_true", help="Seed all scenarios into distinct run directories")
    args = parser.parse_args()
    if args.command == "validate":
        validate_all()
    elif args.all:
        require(args.run_id is None, "--run-id cannot be combined with --all")
        for name in validate_all():
            seed(name)
    else:
        seed(args.scenario, args.run_id)


if __name__ == "__main__":
    main()
