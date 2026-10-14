"""Transactional authorized mock actions and independent observation-based verification."""

import json

from helpdesk.domain.contracts import Proposal, VerificationResult, new_id
from helpdesk.storage.repository import AccessDenied


def source_rows(db, table):
    return [json.loads(row[0]) for row in db.execute(f"SELECT payload FROM {table}")]


def update_source(db, table, key, value):
    db.execute(f"UPDATE {table} SET payload=? WHERE record_id=?", (json.dumps(value), value[key]))


class ResolutionService:
    def __init__(self, approvals):
        self.approvals = approvals
        self.repository = approvals.repository

    def consent(self, context, operation: str, allow: bool):
        if type(allow) is not bool:
            raise ValueError("Consent must be explicit boolean")
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            if case.status != "awaiting_employee" or case.facts.get("pending_consent", {}).get("operation") != operation:
                raise ValueError("No matching pending consent request")
            facts = dict(case.facts)
            facts.pop("pending_consent", None)
            allowed = set(facts.get("consent_operations", []))
            if allow:
                allowed.add(operation)
            else:
                allowed.discard(operation)
            facts["consent_operations"] = sorted(allowed)
            facts["last_consent"] = {"operation": operation, "allowed": allow}
            self.repository.update_case(db, case, context.clock.now(), status="investigating", facts=facts)
            self.approvals._audit(db, "employee_consent", context.employee_id, context.clock.now(), case_id=case.case_id, operation=operation, allowed=allow)

    def handle_proposal(self, context, action, request_id):
        proposal, approval = self.approvals.propose(context, action, request_id)
        if approval and approval.status == "pending":
            with self.repository.transaction() as db:
                case = self.repository._owned_case(db, context)
                self.repository.update_case(db, case, context.clock.now(), status="awaiting_approval", facts={**case.facts, "pending_proposal_id": proposal.proposal_id, "approval_id": approval.approval_id})
            return {"status": "awaiting_approval", "approval_id": approval.approval_id, "stop": True, "message": "Your request is awaiting your manager's approval. No access has been granted. You can check the approval status here."}
        if proposal.decision.decision == "deny":
            return {"status": "denied", "reason": proposal.decision.reason, "proposal_id": proposal.proposal_id}
        record = self.execute(context, proposal.proposal_id)
        return {**record, "stop": record["status"] == "success", "message": "The simulated action completed. Please use the feedback control to confirm whether the issue is fixed." if record["status"] == "success" else "The action was refused after a fresh authorization check."}

    def execute(self, context, proposal_id):
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            row = db.execute("SELECT payload FROM proposals WHERE record_id=?", (proposal_id,)).fetchone()
            if row is None:
                raise AccessDenied("Proposal unavailable")
            proposal = Proposal.model_validate_json(row[0])
            if proposal.case_id != case.case_id or proposal.employee_id != context.employee_id:
                raise AccessDenied("Proposal scope mismatch")
            previous = db.execute("SELECT payload FROM actions WHERE json_extract(payload,'$.proposal_id')=?", (proposal_id,)).fetchone()
            if previous:
                return json.loads(previous[0])
            if not self.approvals.authorized_in_transaction(db, context, case, proposal_id):
                self.approvals._audit(db, "action_refused", context.employee_id, context.clock.now(), proposal_id=proposal_id, case_id=case.case_id)
                return {"status": "denied", "proposal_id": proposal_id, "reason": "Current authorization is not sufficient"}
            op = proposal.action.operation
            if op == "unlock_demo_account":
                row = next(r for r in source_rows(db, "account_states") if r["employee_id"] == context.employee_id and r["service_id"] == "okta")
                row.update(status="active", failed_attempts=0, observed_at=context.clock.now().isoformat())
                update_source(db, "account_states", "account_id", row)
                details = {"account_id": row["account_id"], "status": "active"}
            elif op == "refresh_demo_vpn_profile":
                device = next(r for r in source_rows(db, "devices") if r["device_id"] == proposal.action.parameters["device_id"])
                device["vpn_profile_revision"] = device["required_vpn_profile_revision"]
                update_source(db, "devices", "device_id", device)
                for snapshot in source_rows(db, "diagnostic_snapshots"):
                    if snapshot["device_id"] == device["device_id"] and snapshot["service_id"] == "vpn":
                        snapshot["observations"].update(profile_revision=device["vpn_profile_revision"], last_error=None, disconnect_interval_minutes=None)
                        snapshot["observed_at"] = context.clock.now().isoformat()
                        update_source(db, "diagnostic_snapshots", "snapshot_id", snapshot)
                details = {"device_id": device["device_id"], "profile_revision": device["vpn_profile_revision"]}
            elif op == "grant_demo_access":
                existing = next((r for r in source_rows(db, "access_grants") if r["employee_id"] == context.employee_id and r["resource_id"] == proposal.action.resource_id and r["role"] == proposal.action.parameters["role"] and r["status"] == "active"), None)
                if not existing:
                    approval_row = db.execute("SELECT record_id FROM approvals WHERE json_extract(payload,'$.proposal_id')=?", (proposal_id,)).fetchone()
                    existing = {"grant_id": new_id("GRANT"), "employee_id": context.employee_id, "resource_id": proposal.action.resource_id, "environment": proposal.action.environment, "role": proposal.action.parameters["role"], "status": "active", "granted_at": context.clock.now().isoformat(), "approval_id": approval_row[0] if approval_row else None}
                    db.execute("INSERT INTO access_grants VALUES (?,?)", (existing["grant_id"], json.dumps(existing)))
                details = existing
            else:
                return {"status": "denied", "proposal_id": proposal_id, "reason": "No executable mock handler"}
            record = {"action_id": new_id("ACTION"), "proposal_id": proposal_id, "case_id": case.case_id, "employee_id": context.employee_id, "operation": op, "status": "success", "details": details, "executed_at": context.clock.now().isoformat()}
            db.execute("INSERT INTO actions VALUES (?,?)", (record["action_id"], json.dumps(record)))
            facts = {**case.facts, "last_proposal_id": proposal_id}
            facts.pop("pending_proposal_id", None)
            self.repository.update_case(db, case, context.clock.now(), status="awaiting_verification", facts=facts, attempted_fixes=[*case.attempted_fixes, record])
            self.approvals._audit(db, "action_executed", context.employee_id, context.clock.now(), action_id=record["action_id"], case_id=case.case_id, proposal_id=proposal_id)
            return record

    def verify(self, context, proposal_id, employee_feedback: bool | None = None):
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            if case.status != "awaiting_verification" or case.facts.get("last_proposal_id") != proposal_id:
                raise ValueError("No matching action awaiting verification")
            if employee_feedback is not None and type(employee_feedback) is not bool:
                raise ValueError("Feedback must be a boolean")
            proposal = Proposal.model_validate_json(db.execute("SELECT payload FROM proposals WHERE record_id=?", (proposal_id,)).fetchone()[0])
            operation = proposal.action.operation
            observations = {}
            if operation == "unlock_demo_account":
                account = next(r for r in source_rows(db, "account_states") if r["employee_id"] == context.employee_id and r["service_id"] == "okta")
                success = account["status"] == "active"
                observations = {"account_active": success}
            elif operation == "refresh_demo_vpn_profile":
                device = next(r for r in source_rows(db, "devices") if r["device_id"] == proposal.action.parameters["device_id"])
                employee = next(e for e in source_rows(db, "employees") if e["employee_id"] == context.employee_id)
                incident = any(r["status"] != "resolved" and "vpn" in r["service_ids"] and (not r["affected_locations"] or employee["location"] in r["affected_locations"]) for r in source_rows(db, "incidents"))
                status = next(r for r in source_rows(db, "services") if r["service_id"] == "vpn")
                status_applies = status["region"] in {"global", device["region"]} and (not status["affected_locations"] or employee["location"] in status["affected_locations"])
                success = device["vpn_profile_revision"] == device["required_vpn_profile_revision"] and not incident and (not status_applies or status["health"] == "healthy")
                observations = {"profile_current": device["vpn_profile_revision"] == device["required_vpn_profile_revision"], "applicable_incident": incident, "service_health": status["health"], "service_status_applies": status_applies}
            else:
                resource = next(r for r in source_rows(db, "resources") if r["resource_id"] == proposal.action.resource_id)
                grants = source_rows(db, "access_grants")
                grant = next((g for g in grants if g["employee_id"] == context.employee_id and g["resource_id"] == resource["resource_id"] and g["environment"] == resource["environment"] and g["role"] == proposal.action.parameters["role"] and g["status"] == "active"), None)
                service = next(r for r in source_rows(db, "services") if r["service_id"] == resource["service_id"])
                success = bool(grant and service["health"] == "healthy")
                observations = {"grant_active": bool(grant), "resource_probe_passed": success, "service_health": service["health"]}
            confirmed = employee_feedback is True
            failed = not success or employee_feedback is False
            remaining = []
            if operation == "grant_demo_access":
                for rid in case.facts.get("required_resources", []):
                    resource = next(r for r in source_rows(db, "resources") if r["resource_id"] == rid)
                    expected_role = "reader" if rid.startswith("snowflake") else "viewer"
                    exists = any(g["employee_id"] == context.employee_id and g["resource_id"] == rid and g["role"] == expected_role and g["status"] == "active" for g in source_rows(db, "access_grants"))
                    healthy = next(r for r in source_rows(db, "services") if r["service_id"] == resource["service_id"])["health"] == "healthy"
                    if not exists or not healthy:
                        remaining.append(rid)
                observations["remaining_resources"] = remaining
            result = VerificationResult(outcome="failure" if failed else "success", method="independent_runtime_observation_and_employee_feedback", observations=observations, employee_confirmation_required=True, employee_confirmed=confirmed)
            status = "investigating" if failed or remaining else "resolved" if confirmed else "awaiting_verification"
            # Feedback is explicitly for the whole reported issue, not HTTP success.
            self.repository.update_case(db, case, context.clock.now(), status=status, verification=result, attempted_fixes=[{**item, "verification": result.model_dump(mode="json")} if item["proposal_id"] == proposal_id else item for item in case.attempted_fixes])
            self.approvals._audit(db, "outcome_verified", context.employee_id, context.clock.now(), case_id=case.case_id, outcome=result.outcome, employee_confirmed=confirmed, observations=observations)
            return result
