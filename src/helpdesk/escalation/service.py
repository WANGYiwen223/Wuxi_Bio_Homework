"""Human handoff built from persisted facts, never a generated success claim."""

import json
from typing import Literal

from helpdesk.domain.contracts import EvidenceRecord, Message, new_id
from helpdesk.observability.redaction import redact
from helpdesk.storage.repository import AccessDenied

IssueCategory = Literal[
    "security_incident", "network_connectivity", "pipeline_infrastructure",
    "account_access", "peripheral_hardware", "software_install", "access_inquiry", "other",
]

# Queue assignment is backend policy. The model declares what the problem IS; it never
# picks a queue, and evidence or keyword substrings never reroute the case (P2).
ISSUE_GROUPS = {
    "security_incident": "security",
    "network_connectivity": "network",
    "pipeline_infrastructure": "sre",
    "account_access": "helpdesk",
    "peripheral_hardware": "helpdesk",
    "software_install": "helpdesk",
    "access_inquiry": "helpdesk",
    "other": "helpdesk",
}

# Phrase-level safety net over employee text; it can only escalate to security.
_SECURITY_PHRASES = (
    "was stolen", "stolen from", "lost my phone", "lost my laptop", "lost my company phone",
    "phishing", "clicked the link", "typed my password", "entered my password", "suspicious login",
)
_NEGATIONS = ("no ", "not ", "n't", "never ")


def _reports_security(text: str) -> bool:
    for phrase in _SECURITY_PHRASES:
        start = 0
        while True:
            hit = text.find(phrase, start)
            if hit == -1:
                break
            if not any(n in text[max(0, hit - 12):hit] for n in _NEGATIONS):
                return True
            start = hit + 1
    return False


def route_group(category: IssueCategory | None, employee_text: str) -> tuple[str, str]:
    """Return (support_group, routing_basis). Internal fallbacks triage to helpdesk."""
    if category is None:
        group, basis = "helpdesk", "internal_fallback"
    else:
        if category not in ISSUE_GROUPS:
            raise ValueError(f"Unknown issue category: {category}")
        group, basis = ISSUE_GROUPS[category], "model_declared"
    if group != "security" and _reports_security(employee_text):
        group, basis = "security", "backend_override"
    return group, basis


class HandoffService:
    def __init__(self, repository):
        self.repository = repository

    def create(self, context, reason: str, category: IssueCategory | None = None):
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            if case.handoff_id:
                existing = json.loads(db.execute("SELECT payload FROM handoffs WHERE record_id=?", (case.handoff_id,)).fetchone()[0])
                return {"status": existing["status"], "handoff_id": case.handoff_id, "message": f"This case has already been handed to {existing['support_group']}. Current status: {existing['status']}."}
            if case.status == "resolved":
                raise ValueError("Open a new case for a resolved issue")
            messages = [Message.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM messages WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (case.case_id,))]
            evidence = [EvidenceRecord.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM evidence WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (case.case_id,))]
            symptoms = [m.text for m in messages if m.role == "employee"]
            issue = symptoms[0] if symptoms else "Investigation requires human review"
            group, basis = route_group(category, " ".join(symptoms).lower())
            package = {
                "handoff_id": new_id("HANDOFF"), "case_id": case.case_id,
                "employee_id": context.employee_id, "support_group": group,
                "issue_category": category, "routing_basis": basis,
                "status": "queued", "created_at": context.clock.now().isoformat(),
                "issue_summary": redact(issue), "employee_updates": symptoms[1:],
                "impact": case.facts.get("impact", "Not yet confirmed"),
                "reason": redact(reason), "confirmed_facts": case.facts,
                "evidence": [e.model_dump(mode="json") for e in evidence],
                "attempted_fixes": case.attempted_fixes, "tool_errors": case.tool_errors,
                "unresolved_questions": case.missing_information,
                "suggested_next_step": "Review source timestamps and attempted-fix outcomes, then continue investigation within IT authority.",
                "acknowledged_by": None, "acknowledged_at": None,
            }
            db.execute("INSERT INTO handoffs VALUES (?,?)", (package["handoff_id"], json.dumps(package)))
            self.repository.update_case(db, case, context.clock.now(), status="escalated", handoff_id=package["handoff_id"])
            self.repository.audit(db, {"event": "handoff_created", "case_id": case.case_id, "handoff_id": package["handoff_id"], "actor_id": context.employee_id, "created_at": context.clock.now().isoformat()})
            return {"status": "queued", "handoff_id": package["handoff_id"], "message": f"I queued your case for {group} with the investigation context. A specialist has not acknowledged it yet."}

    def _reviewer(self, db, session_id):
        employee_id, verified = self.repository._session(db, session_id)
        row = db.execute("SELECT payload FROM employees WHERE record_id=?", (employee_id,)).fetchone()
        reviewer = json.loads(row[0]) if row else None
        if not verified or not reviewer or reviewer["account_status"] != "active" or not {"it_reviewer", "security_reviewer"} & set(reviewer["roles"]):
            raise AccessDenied("Specialist role required")
        return reviewer

    @staticmethod
    def _visible(reviewer, package):
        required = "security_reviewer" if package["support_group"] == "security" else "it_reviewer"
        return required in reviewer["roles"]

    def queue(self, session_id):
        with self.repository.transaction() as db:
            reviewer = self._reviewer(db, session_id)
            rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM handoffs ORDER BY rowid")]
            return [row for row in rows if self._visible(reviewer, row)]

    def acknowledge(self, session_id, handoff_id, clock):
        with self.repository.transaction() as db:
            reviewer = self._reviewer(db, session_id)
            row = db.execute("SELECT payload FROM handoffs WHERE record_id=?", (handoff_id,)).fetchone()
            if not row:
                raise AccessDenied("Handoff unavailable")
            package = json.loads(row[0])
            if not self._visible(reviewer, package):
                raise AccessDenied("Specialist group mismatch")
            if package["status"] == "acknowledged":
                return package
            package.update(status="acknowledged", acknowledged_by=reviewer["employee_id"], acknowledged_at=clock.now().isoformat())
            db.execute("UPDATE handoffs SET payload=? WHERE record_id=?", (json.dumps(package), handoff_id))
            self.repository.audit(db, {"event": "handoff_acknowledged", "case_id": package["case_id"], "actor_id": reviewer["employee_id"], "created_at": clock.now().isoformat()})
            return package
