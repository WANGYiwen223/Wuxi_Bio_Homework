"""SQLite source/case repositories with session scope and optimistic updates."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import secrets

from helpdesk.bootstrap.context import Clock, ToolContext
from helpdesk.domain.contracts import Case, EvidenceRecord, Message, new_id
from helpdesk.observability.events import log_event

SOURCE_TABLES = {"employees", "devices", "resources", "access_grants", "services", "incidents", "changes", "account_states", "diagnostic_snapshots", "resolution_history"}
RECORD_TABLES = {"cases", "messages", "evidence", "proposals", "approvals", "actions", "handoffs", "audit_events"}


class AccessDenied(Exception):
    pass


class RevisionConflict(Exception):
    pass


class AuditConnection(sqlite3.Connection):
    """Buffer log delivery until its owning transaction commits."""

    pending_events: list


class Repository:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError("Seed the demo database before opening the repository")
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, identity_verified INTEGER NOT NULL)")
            for table in RECORD_TABLES:
                db.execute(f"CREATE TABLE IF NOT EXISTS {table} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            columns = {r[1] for r in db.execute("PRAGMA table_info(cases)")}
            for name, kind in {"owner_id": "TEXT", "version": "INTEGER NOT NULL DEFAULT 0"}.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE cases ADD COLUMN {name} {kind}")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_approval_per_proposal ON approvals(json_extract(payload, '$.proposal_id'))")
            db.execute("CREATE TABLE IF NOT EXISTS proposal_receipts (request_key TEXT PRIMARY KEY, proposal_id TEXT NOT NULL)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_action_per_proposal ON actions(json_extract(payload, '$.proposal_id'))")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5, factory=AuditConnection)
        db.pending_events = []
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
            for event in db.pending_events:
                log_event(event)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def source(self, table: str, identifier: str) -> dict | None:
        if table not in SOURCE_TABLES:
            raise ValueError("Unknown source collection")
        with sqlite3.connect(self.path) as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE record_id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def sources(self, table: str) -> list[dict]:
        if table not in SOURCE_TABLES:
            raise ValueError("Unknown source collection")
        with sqlite3.connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute(f"SELECT payload FROM {table} ORDER BY record_id")]

    def create_demo_session(self, employee_id: str) -> str:
        if self.source("employees", employee_id) is None:
            raise ValueError("Unknown demo employee")
        session = secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session, employee_id, 1))
        return session

    @staticmethod
    def _session(db, session_id):
        row = db.execute("SELECT employee_id, identity_verified FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is None:
            raise AccessDenied("Invalid session")
        return row

    def create_case(self, session_id: str, clock: Clock) -> Case:
        with self.transaction() as db:
            employee_id, _ = self._session(db, session_id)
            case = Case(session_id=session_id, employee_id=employee_id, created_at=clock.now(), updated_at=clock.now())
            db.execute("INSERT INTO cases(record_id,payload,owner_id,version) VALUES (?,?,?,?)", (case.case_id, case.model_dump_json(), employee_id, 0))
        return case

    @staticmethod
    def _owned_case(db, context: ToolContext):
        employee_id, verified = Repository._session(db, context.session_id)
        if employee_id != context.employee_id or bool(verified) != context.identity_verified:
            raise AccessDenied("Context does not match trusted session")
        row = db.execute("SELECT payload FROM cases WHERE record_id=? AND owner_id=?", (context.case_id, employee_id)).fetchone()
        if row is None:
            raise AccessDenied("Case is not accessible")
        case = Case.model_validate_json(row[0])
        if case.session_id != context.session_id:
            raise AccessDenied("Case belongs to a different session")
        return case

    def context(self, session_id: str, case_id: str, clock: Clock) -> ToolContext:
        with self.transaction() as db:
            employee_id, verified = self._session(db, session_id)
            ctx = ToolContext(session_id, employee_id, case_id, bool(verified), clock)
            self._owned_case(db, ctx)
            return ctx

    def get_case(self, context: ToolContext) -> Case:
        with self.transaction() as db:
            return self._owned_case(db, context)

    def save_case(self, context: ToolContext, case: Case) -> Case:
        with self.transaction() as db:
            current = self._owned_case(db, context)
            if (case.case_id, case.employee_id, case.session_id, case.created_at) != (current.case_id, current.employee_id, current.session_id, current.created_at):
                raise AccessDenied("Cannot change case identity")
            if case.version != current.version:
                raise RevisionConflict("Case changed; reload before applying updates")
            if case.updated_at < current.updated_at:
                raise ValueError("Case timestamp cannot move backwards")
            from helpdesk.domain.lifecycle import TRANSITIONS
            if case.status != current.status and case.status not in TRANSITIONS[current.status]:
                raise ValueError("Invalid persisted lifecycle transition")
            saved = Case.model_validate({**case.model_dump(), "version": case.version + 1})
            db.execute("UPDATE cases SET payload=?,version=? WHERE record_id=?", (saved.model_dump_json(), saved.version, saved.case_id))
            return saved

    def append_message(self, context: ToolContext, role: str, text: str) -> Message:
        msg = Message(case_id=context.case_id, employee_id=context.employee_id, role=role, text=text, created_at=context.clock.now())
        with self.transaction() as db:
            self._owned_case(db, context)
            db.execute("INSERT INTO messages VALUES (?,?)", (msg.message_id, msg.model_dump_json()))
        return msg

    def messages(self, context: ToolContext) -> list[Message]:
        with self.transaction() as db:
            self._owned_case(db, context)
            return [Message.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM messages WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (context.case_id,))]

    def record_tool(self, context: ToolContext, tool_name: str, result, evidence: list[EvidenceRecord]):
        with self.transaction() as db:
            self._owned_case(db, context)
            for item in evidence:
                if item.case_id != context.case_id or item.employee_id != context.employee_id:
                    raise AccessDenied("Evidence scope mismatch")
                db.execute("INSERT INTO evidence VALUES (?,?)", (item.evidence_id, item.model_dump_json()))
            event = {"case_id": context.case_id, "employee_id": context.employee_id, "event": "tool_result", "tool_name": tool_name, "tool_call_id": result.tool_call_id, "status": result.status, "evidence_ids": [e.evidence_id for e in evidence], "error_code": result.error.code if result.error else None, "created_at": context.clock.now().isoformat()}
            self.audit(db, event)

    def evidence(self, context: ToolContext) -> list[EvidenceRecord]:
        with self.transaction() as db:
            self._owned_case(db, context)
            return [EvidenceRecord.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM evidence WHERE json_extract(payload,'$.case_id')=? ORDER BY rowid", (context.case_id,))]

    @staticmethod
    def update_case(db, case, now, status=None, **updates):
        """Persist a lifecycle change inside the caller's mutation transaction."""
        from helpdesk.domain.lifecycle import transition
        changed = transition(case, status or case.status, now, **updates)
        saved = Case.model_validate({**changed.model_dump(), "version": case.version + 1})
        db.execute("UPDATE cases SET payload=?,version=? WHERE record_id=? AND version=?", (saved.model_dump_json(), saved.version, case.case_id, case.version))
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            raise RevisionConflict("Case changed concurrently")
        return saved

    def trace(self, context, event, metrics):
        with self.transaction() as db:
            self._owned_case(db, context)
            payload = {"case_id": context.case_id, "event": event, "created_at": context.clock.now().isoformat(), **metrics}
            self.audit(db, payload)

    @staticmethod
    def audit(db, payload):
        payload = {**payload, "recorded_at": datetime.now(timezone.utc).isoformat()}
        cursor = db.execute("INSERT INTO audit_events VALUES (?,?)", (new_id("AUDIT"), json.dumps(payload)))
        db.pending_events.append({**payload, "sequence": cursor.lastrowid})

    def events(self, context, after=0, limit=200):
        with self.transaction() as db:
            self._owned_case(db, context)
            rows = db.execute("SELECT rowid,payload FROM audit_events WHERE rowid>? AND json_extract(payload,'$.case_id')=? ORDER BY rowid LIMIT ?", (after, context.case_id, limit))
            return [{**json.loads(row[1]), "sequence": row[0]} for row in rows]
