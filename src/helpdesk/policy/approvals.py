"""Durable proposals and reviewer decisions bound to immutable action scope."""

from datetime import timedelta
import json

from helpdesk.domain.contracts import ActionRequest, Approval, Case, Proposal
from helpdesk.policy.engine import PolicyEngine, scope_hash
from helpdesk.storage.repository import AccessDenied, Repository


class ApprovalService:
    def __init__(self, engine: PolicyEngine):
        self.engine = engine
        self.repository = engine.repository

    def propose(self, context, action: ActionRequest, request_id: str | None = None) -> tuple[Proposal, Approval | None]:
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            request_key = f"{case.case_id}:{request_id}" if request_id else None
            receipt = db.execute("SELECT proposal_id FROM proposal_receipts WHERE request_key=?", (request_key,)).fetchone() if request_key else None
            if receipt:
                proposal = Proposal.model_validate_json(db.execute("SELECT payload FROM proposals WHERE record_id=?", (receipt[0],)).fetchone()[0])
                if proposal.action != action:
                    raise ValueError("Request ID reused with different action scope")
                row = db.execute("SELECT payload FROM approvals WHERE json_extract(payload,'$.proposal_id')=?", (proposal.proposal_id,)).fetchone()
                return proposal, Approval.model_validate_json(row[0]) if row else None
            decision = self.engine._evaluate(context, action, case, db)
            proposal = Proposal(case_id=case.case_id, employee_id=context.employee_id, action=action, decision=decision, scope_hash=scope_hash(context.employee_id, case.case_id, action, decision.policy_version), created_at=context.clock.now())
            approval = None
            if decision.decision == "approval_required":
                employee = json.loads(db.execute("SELECT payload FROM employees WHERE record_id=?", (context.employee_id,)).fetchone()[0])
                approver_id = employee.get("manager_id") if decision.approver_role == "manager" else None
                row = db.execute("SELECT payload FROM employees WHERE record_id=?", (approver_id,)).fetchone() if approver_id else None
                reviewer = json.loads(row[0]) if row else None
                if not reviewer or reviewer["account_status"] != "active" or decision.approver_role not in reviewer["roles"] or approver_id == context.employee_id:
                    raise AccessDenied("No eligible reviewer for this proposal")
                ttl = self.engine._policy()["approval_ttl_seconds"]
                approval = Approval(proposal_id=proposal.proposal_id, case_id=case.case_id, employee_id=context.employee_id, approver_id=approver_id, scope_hash=proposal.scope_hash, policy_version=decision.policy_version, created_at=context.clock.now(), expires_at=context.clock.now() + timedelta(seconds=ttl))
                db.execute("INSERT INTO approvals VALUES (?,?)", (approval.approval_id, approval.model_dump_json()))
            db.execute("INSERT INTO proposals VALUES (?,?)", (proposal.proposal_id, proposal.model_dump_json()))
            if request_key:
                db.execute("INSERT INTO proposal_receipts VALUES (?,?)", (request_key, proposal.proposal_id))
            self._audit(db, "action_proposed", context.employee_id, context.clock.now(), proposal_id=proposal.proposal_id, decision=decision.decision, case_id=case.case_id)
        return proposal, approval

    @staticmethod
    def _audit(db, event, actor_id, now, **detail):
        Repository.audit(db, {"event": event, "actor_id": actor_id, "created_at": now.isoformat(), **detail})

    @staticmethod
    def _reviewer(db, session_id):
        employee_id, verified = Repository._session(db, session_id)
        row = db.execute("SELECT payload FROM employees WHERE record_id=?", (employee_id,)).fetchone()
        if not verified or not row:
            raise AccessDenied("Reviewer session is unavailable")
        reviewer = json.loads(row[0])
        if reviewer["account_status"] != "active":
            raise AccessDenied("Reviewer is inactive")
        return reviewer

    def pending(self, reviewer_session: str, clock) -> list[Approval]:
        with self.repository.transaction() as db:
            reviewer = self._reviewer(db, reviewer_session)
            rows = db.execute("SELECT payload FROM approvals WHERE json_extract(payload,'$.approver_id')=?", (reviewer["employee_id"],))
            return [a for a in (Approval.model_validate_json(row[0]) for row in rows) if a.status == "pending" and a.expires_at > clock.now()]

    def decide(self, reviewer_session: str, approval_id: str, approve: bool, clock) -> Approval:
        if type(approve) is not bool:
            raise ValueError("Approval decision must be a boolean")
        with self.repository.transaction() as db:
            reviewer = self._reviewer(db, reviewer_session)
            row = db.execute("SELECT payload FROM approvals WHERE record_id=?", (approval_id,)).fetchone()
            if row is None:
                raise AccessDenied("Approval unavailable")
            approval = Approval.model_validate_json(row[0])
            proposal = Proposal.model_validate_json(db.execute("SELECT payload FROM proposals WHERE record_id=?", (approval.proposal_id,)).fetchone()[0])
            employee = json.loads(db.execute("SELECT payload FROM employees WHERE record_id=?", (approval.employee_id,)).fetchone()[0])
            if reviewer["employee_id"] != approval.approver_id or reviewer["employee_id"] == approval.employee_id or "manager" not in reviewer["roles"] or employee["manager_id"] != reviewer["employee_id"]:
                raise AccessDenied("Only the current scoped manager may decide")
            if approval.status != "pending":
                raise ValueError("Approval already decided")
            if clock.now() >= approval.expires_at:
                updated = Approval.model_validate({**approval.model_dump(), "status": "expired"})
            else:
                case = Case.model_validate_json(db.execute("SELECT payload FROM cases WHERE record_id=?", (approval.case_id,)).fetchone()[0])
                from helpdesk.bootstrap.context import ToolContext
                requester_session = self.repository._session(db, case.session_id)
                ctx = ToolContext(case.session_id, case.employee_id, case.case_id, bool(requester_session[1]), clock)
                current = self.engine._evaluate(ctx, proposal.action, case, db)
                if current.decision != "approval_required" or current.policy_version != approval.policy_version or scope_hash(approval.employee_id, approval.case_id, proposal.action, current.policy_version) != approval.scope_hash or current.approver_role != proposal.decision.approver_role:
                    raise ValueError("Proposal scope or current policy changed; create a new proposal")
                updated = Approval.model_validate({**approval.model_dump(), "status": "approved" if approve else "rejected", "decided_by": reviewer["employee_id"], "decided_at": clock.now()})
            db.execute("UPDATE approvals SET payload=? WHERE record_id=?", (updated.model_dump_json(), approval_id))
            self._audit(db, "approval_decided", reviewer["employee_id"], clock.now(), approval_id=approval_id, status=updated.status, case_id=approval.case_id)
            return updated

    def is_authorized(self, context, proposal_id: str) -> bool:
        """Re-evaluate a stored proposal before a future executor may use it."""
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            return self.authorized_in_transaction(db, context, case, proposal_id)

    def authorized_in_transaction(self, db, context, case, proposal_id):
        row = db.execute("SELECT payload FROM proposals WHERE record_id=?", (proposal_id,)).fetchone()
        if row is None:
            return False
        proposal = Proposal.model_validate_json(row[0])
        if proposal.case_id != case.case_id or proposal.employee_id != context.employee_id:
            return False
        current = self.engine._evaluate(context, proposal.action, case, db)
        if current.policy_version != proposal.decision.policy_version or proposal.scope_hash != scope_hash(context.employee_id, case.case_id, proposal.action, current.policy_version):
            return False
        if current.decision == "allow":
            return proposal.decision.decision == "allow"
        if current.decision != "approval_required":
            return False
        row = db.execute("SELECT payload FROM approvals WHERE json_extract(payload,'$.proposal_id')=?", (proposal_id,)).fetchone()
        if row is None:
            return False
        a = Approval.model_validate_json(row[0])
        employee = json.loads(db.execute("SELECT payload FROM employees WHERE record_id=?", (context.employee_id,)).fetchone()[0])
        reviewer_row = db.execute("SELECT payload FROM employees WHERE record_id=?", (a.approver_id,)).fetchone()
        reviewer = json.loads(reviewer_row[0]) if reviewer_row else {}
        return bool(a.status == "approved" and a.scope_hash == proposal.scope_hash and a.policy_version == current.policy_version and a.created_at <= context.clock.now() < a.expires_at and employee["manager_id"] == a.approver_id and reviewer.get("account_status") == "active" and current.approver_role in reviewer.get("roles", []))
