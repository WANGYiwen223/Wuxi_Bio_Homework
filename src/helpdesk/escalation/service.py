"""Human handoff built from persisted facts, never a generated success claim."""

import json

from helpdesk.domain.contracts import EvidenceRecord, Message, new_id
from helpdesk.observability.redaction import redact
from helpdesk.storage.repository import AccessDenied


class HandoffService:
    def __init__(self, repository):
        self.repository = repository

    def create(self, context, reason: str):
        with self.repository.transaction() as db:
            case = self.repository._owned_case(db, context)
            if case.handoff_id:
                existing = json.loads(db.execute("SELECT payload FROM handoffs WHERE record_id=?", (case.handoff_id,)).fetchone()[0])
                return {"status": existing["status"], "handoff_id": case.handoff_id, "message": f"This case is already queued for {existing['support_group']} ({case.handoff_id})."}
            if case.status == "resolved":
                raise ValueError("Open a new case for a resolved issue")
            messages = [Message.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM messages WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (case.case_id,))]
            evidence = [EvidenceRecord.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM evidence WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (case.case_id,))]
            symptoms = [m.text for m in messages if m.role == "employee"]
            issue = symptoms[0] if symptoms else "Investigation requires human review"
            text = (" ".join(symptoms) + " " + reason).lower()
            services = {e.facts.get("service_id") for e in evidence if isinstance(e.facts, dict)}
            group = "security" if any(s in text for s in ["breach", "compromise", "suspicious login"]) else "sre" if {"jenkins", "tableau"} & services else "network" if "vpn" in services else "helpdesk"
            package = {
                "handoff_id": new_id("HANDOFF"), "case_id": case.case_id,
                "employee_id": context.employee_id, "support_group": group,
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
            db.execute("INSERT INTO audit_events VALUES (?,?)", (new_id("AUDIT"), json.dumps({"event": "handoff_created", "case_id": case.case_id, "handoff_id": package["handoff_id"], "actor_id": context.employee_id, "created_at": context.clock.now().isoformat()})))
            return {"status": "queued", "handoff_id": package["handoff_id"], "message": f"I queued your case for {group} with the investigation context ({package['handoff_id']}). A specialist has not acknowledged it yet."}

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
            db.execute("INSERT INTO audit_events VALUES (?,?)", (new_id("AUDIT"), json.dumps({"event": "handoff_acknowledged", "case_id": package["case_id"], "actor_id": reviewer["employee_id"], "created_at": clock.now().isoformat()})))
            return package
