"""Composition root for the local demo application."""

from datetime import datetime
import json
from pathlib import Path

from helpdesk.bootstrap.context import DemoClock
from helpdesk.bootstrap.settings import Settings
from helpdesk.domain.contracts import VerificationResult
from helpdesk.domain.lifecycle import transition
from helpdesk.escalation.service import HandoffService
from helpdesk.models.client import CompatibleChatModel
from helpdesk.policy.approvals import ApprovalService
from helpdesk.policy.engine import PolicyEngine
from helpdesk.resolution.service import ResolutionService
from helpdesk.storage.repository import Repository
from helpdesk.tools.read_tools import ReadTools
from helpdesk.workflow.agent import DiagnosticAgent


class Runtime:
    def __init__(self, repository, settings, clock, knowledge_dir, policy_path, checkpoint_path, model=None, faults=None):
        self.repository, self.settings, self.clock = repository, settings, clock
        self.reads = ReadTools(repository, knowledge_dir, faults)
        self.approvals = ApprovalService(PolicyEngine(repository, policy_path))
        self.resolution = ResolutionService(self.approvals)
        self.handoffs = HandoffService(repository)
        self.agent = DiagnosticAgent(repository, self.reads, model or CompatibleChatModel(settings), settings, checkpoint_path, self.resolution.handle_proposal, self.handoffs.create)

    @classmethod
    def local(cls, root: Path):
        settings = Settings.load(root)
        manifest_path = settings.run_dir / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Seed a demo run before starting the server; see README")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls(Repository(settings.run_dir / "helpdesk.sqlite"), settings, DemoClock(datetime.fromisoformat(manifest["clock"])), root / "data/knowledge", root / "data/policies/action_rules.json", settings.run_dir / "checkpoints.sqlite", faults=manifest.get("faults", []))

    def context(self, session, case_id):
        return self.repository.context(session, case_id, self.clock)

    def feedback(self, context, resolved: bool):
        case = self.repository.get_case(context)
        if case.status == "awaiting_verification":
            result = self.resolution.verify(context, case.facts["last_proposal_id"], resolved)
            message = "Verified: the reported issue is resolved." if self.repository.get_case(context).status == "resolved" else "The result is not sufficient to close the issue. Continue describing what remains unresolved."
            self.repository.append_message(context, "employee", "Explicit whole-issue feedback: " + str(resolved))
            self.repository.append_message(context, "assistant", message)
            return {"message": message, "verification": result.model_dump(mode="json")}
        if case.status != "awaiting_employee" or case.facts.get("last_response_kind") != "guidance":
            raise ValueError("There is no proposed fix awaiting feedback")
        knowledge = [e for e in self.repository.evidence(context) if e.source.source_type == "knowledge"]
        if not knowledge:
            raise ValueError("Documented guidance evidence is required")
        verification = VerificationResult(outcome="success" if resolved else "failure", method="employee_confirmed_documented_guidance", employee_confirmation_required=True, employee_confirmed=resolved)
        self.repository.save_case(context, transition(case, "resolved" if resolved else "investigating", self.clock.now(), verification=verification))
        return {"message": "Employee-confirmed guidance outcome recorded.", "verification": verification.model_dump(mode="json")}

    def reviewer_decision(self, reviewer_session, approval_id, approve):
        decision = self.approvals.decide(reviewer_session, approval_id, approve, self.clock)
        with self.repository.transaction() as db:
            from helpdesk.domain.contracts import Case
            case = Case.model_validate_json(db.execute("SELECT payload FROM cases WHERE record_id=?", (decision.case_id,)).fetchone()[0])
        ctx = self.context(case.session_id, case.case_id)
        if decision.status != "approved":
            result = self.handoffs.create(ctx, f"Manager approval {decision.status}")
        else:
            result = self.resolution.execute(ctx, decision.proposal_id)
            if result["status"] != "success":
                result = self.handoffs.create(ctx, "Approved request failed a fresh authorization check")
            else:
                self.resolution.verify(ctx, decision.proposal_id)
                result["message"] = "Manager approval received; the simulated grant completed. Please confirm the whole issue through feedback."
        self.repository.append_message(ctx, "assistant", result["message"])
        return {"approval": decision.model_dump(mode="json"), "result": result}

    def close(self):
        self.agent.close()
