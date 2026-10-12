"""Fail-closed policy evaluation from trusted facts and persisted evidence."""

import hashlib
import json
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from helpdesk.domain.contracts import ActionRequest, EvidenceRecord, PolicyDecision
from helpdesk.storage.repository import Repository


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GrantParameters(Parameters):
    role: str = Field(min_length=1, max_length=30)
    business_justification: str = Field(default="", max_length=1000)


class ProfileParameters(Parameters):
    device_id: str


PARAMETERS = {"unlock_demo_account": Parameters, "refresh_demo_vpn_profile": ProfileParameters, "grant_demo_access": GrantParameters, "modify_production_network": Parameters, "create_handoff": Parameters}
CONDITIONS = {"identity_verified", "target_is_self", "account_state", "employee_consent", "assigned_managed_device", "profile_is_stale", "regional_outage", "department", "environment", "requested_role", "case_owner_verified"}


def scope_hash(employee_id: str, case_id: str, action: ActionRequest, policy_version: str) -> str:
    payload = {"employee_id": employee_id, "case_id": case_id, "action": action.model_dump(mode="json"), "policy_version": policy_version}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class PolicyEngine:
    def __init__(self, repository: Repository, path: Path):
        self.repository = repository
        self.path = path

    def _policy(self):
        policy = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(policy.get("version"), str) or not policy["version"] or not isinstance(policy.get("rules"), list):
            raise ValueError("Policy version and rule list are required")
        if policy.get("default_decision") != "deny" or policy.get("precedence") != ["deny", "approval_required", "allow"]:
            raise ValueError("Policy must fail closed with explicit precedence")
        seen = set()
        for rule in policy["rules"]:
            if rule["rule_id"] in seen or rule["decision"] not in policy["precedence"] or not set(rule["conditions"]) <= CONDITIONS:
                raise ValueError("Invalid policy rule")
            if not rule["resource_scope"] or (rule["decision"] == "approval_required" and not rule["approver_role"]):
                raise ValueError("Invalid scope or approval role")
            seen.add(rule["rule_id"])
        if type(policy["approval_ttl_seconds"]) is not int or policy["approval_ttl_seconds"] <= 0:
            raise ValueError("Invalid approval expiry")
        return policy

    def _rows(self, table, db):
        if db is None:
            return self.repository.sources(table)
        return [json.loads(row[0]) for row in db.execute(f"SELECT payload FROM {table} ORDER BY record_id")]

    def evaluate(self, context, action: ActionRequest) -> PolicyDecision:
        case = self.repository.get_case(context)
        return self._evaluate(context, action, case)

    def _evaluate(self, context, action: ActionRequest, case, db=None):
        try:
            policy = self._policy()
        except (OSError, ValueError, KeyError, TypeError):
            return PolicyDecision(decision="deny", rule_ids=[], policy_version="unavailable", reason="Policy unavailable or invalid")

        def denied(reason):
            return PolicyDecision(decision="deny", rule_ids=[], policy_version=policy["version"], reason=reason)

        if case.status in {"resolved", "escalated"}:
            return denied("Case is closed for new actions")
        if action.operation not in PARAMETERS:
            return denied("Operation is not allowlisted")
        try:
            params = PARAMETERS[action.operation].model_validate(action.parameters)
        except ValueError:
            return denied("Unsupported operation parameters")
        employee = next((r for r in self._rows("employees", db) if r["employee_id"] == context.employee_id), None)
        if not employee or employee["account_status"] != "active":
            return denied("Employee directory account is unavailable or inactive")

        if db is None:
            evidence = self.repository.evidence(context)
        else:
            evidence = [EvidenceRecord.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM evidence WHERE json_extract(payload,'$.case_id')=?", (case.case_id,))]
        by_id = {e.evidence_id: e for e in evidence if e.employee_id == context.employee_id}
        if any(eid not in by_id for eid in action.evidence_ids):
            return denied("Evidence does not belong to this case")
        chosen = [by_id[eid] for eid in action.evidence_ids]
        facts = {
            "identity_verified": context.identity_verified,
            "target_is_self": True,
            "case_owner_verified": True,
            "department": employee["department"],
            "environment": action.environment,
            # Consent is recorded by trusted application input, never action parameters.
            "employee_consent": action.operation in case.facts.get("consent_operations", []),
        }
        service_id = action.resource_id
        if action.operation == "grant_demo_access":
            resource = next((r for r in self._rows("resources", db) if r["resource_id"] == action.resource_id), None)
            if not resource or resource["environment"] != action.environment or params.role not in resource["supported_roles"]:
                return denied("Unsupported resource, environment or role")
            service_id = resource["service_id"]
            facts["requested_role"] = params.role
            if action.environment == "PROD" and not params.business_justification.strip():
                return denied("Production access requires a business justification")
        elif action.operation in {"unlock_demo_account", "refresh_demo_vpn_profile"}:
            expected = "okta" if action.operation == "unlock_demo_account" else "vpn"
            if action.resource_id != expected or action.environment != "INTERNAL":
                return denied("Incorrect operation resource/environment")
            if action.operation == "unlock_demo_account":
                account = next((r for r in self._rows("account_states", db) if r["employee_id"] == context.employee_id and r["service_id"] == "okta"), None)
                facts["account_state"] = account["status"] if account else "unknown"
            else:
                device = next((r for r in self._rows("devices", db) if r["device_id"] == params.device_id), None)
                facts["assigned_managed_device"] = bool(device and device["employee_id"] == context.employee_id and device["managed"])
                facts["profile_is_stale"] = bool(device and device["vpn_profile_revision"] < device["required_vpn_profile_revision"])
                status = next((r for r in self._rows("services", db) if r["service_id"] == "vpn"), None)
                age = (context.clock.now() - datetime.fromisoformat(status["observed_at"])).total_seconds() if status else None
                if age is None or not 0 <= age <= 1800:
                    return denied("Fresh VPN service evidence is required")
                applicable = device and status["region"] in {"global", device["region"]}
                location_matches = not status["affected_locations"] or employee["location"] in status["affected_locations"]
                live_incidents = [r for r in self._rows("incidents", db) if "vpn" in r["service_ids"] and r["status"] != "resolved" and (not r["affected_locations"] or employee["location"] in r["affected_locations"])]
                facts["regional_outage"] = bool(live_incidents or (applicable and location_matches and status["health"] in {"degraded", "outage", "unknown"}))

        if action.operation not in {"create_handoff", "modify_production_network"}:
            documented = any(e.source.source_type == "knowledge" and isinstance(e.facts, dict) and e.facts.get("service_id") == service_id for e in chosen)
            if not documented:
                return denied("Relevant documented procedure evidence is required")
            required_kind = {"unlock_demo_account": "account", "refresh_demo_vpn_profile": "diagnostic", "grant_demo_access": "employee"}[action.operation]
            if not any(e.source.source_type == required_kind and isinstance(e.facts, dict) and (e.facts.get("employee_id") == context.employee_id if required_kind == "employee" else e.facts.get("service_id") == service_id) for e in chosen):
                return denied("Relevant observed target evidence is required")

        matches = [rule for rule in policy["rules"] if rule["operation"] == action.operation and (action.resource_id in rule["resource_scope"] or "*" in rule["resource_scope"]) and all(k in facts and type(facts[k]) is type(v) and facts[k] == v for k, v in rule["conditions"].items())]
        if not matches:
            return denied("No authorization rule matches the trusted facts")
        rank = {decision: i for i, decision in enumerate(policy["precedence"])}
        winner = min(rank[r["decision"]] for r in matches)
        selected = [r for r in matches if rank[r["decision"]] == winner]
        if len({r["approver_role"] for r in selected}) > 1:
            return denied("Conflicting approver requirements")
        return PolicyDecision(decision=selected[0]["decision"], rule_ids=[r["rule_id"] for r in selected], policy_version=policy["version"], reason="Matched deterministic rules using trusted facts", approver_role=selected[0]["approver_role"], verification_requirements=sorted({v for r in selected for v in r["verification_requirements"]}))
