"""Loopback-only demo API with backend-bound employee and reviewer sessions."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from helpdesk.storage.repository import AccessDenied, RevisionConflict
from helpdesk.observability.presentation import activity, present_answer, source_catalog


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionBody(Body):
    employee_id: str


class MessageBody(Body):
    text: str = Field(min_length=1, max_length=12000)


class FeedbackBody(Body):
    resolved: StrictBool


class ConsentBody(Body):
    operation: str
    allow: StrictBool


class DecisionBody(Body):
    approve: StrictBool


def create_app(runtime, ui_dir: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        yield
        runtime.close()

    app = FastAPI(title="Local IT Helpdesk Demo", lifespan=lifespan)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse(status_code=403, content={"detail": "Loopback-only demo"})
        host = request.url.hostname
        if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            return JSONResponse(status_code=403, content={"detail": "Invalid demo host"})
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse(status_code=403, content={"detail": "Cross-origin requests are disabled"})
        return await call_next(request)

    @app.exception_handler(AccessDenied)
    async def denied(request, exc):
        return JSONResponse(status_code=403, content={"detail": "Session or resource is not accessible"})

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RevisionConflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Case changed; reload and retry"})

    def token(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise AccessDenied("Session required")
        return authorization[7:]

    def context(case_id, authorization):
        return runtime.context(token(authorization), case_id)

    @app.get("/health")
    def health():
        return {"status": "ready", "demo_clock": runtime.clock.now().isoformat(), "mode": "synthetic-local-backends"}

    @app.get("/demo/employees")
    def employees():
        return [{k: e[k] for k in ["employee_id", "name", "department", "roles"]} for e in runtime.repository.sources("employees")]

    @app.post("/demo/sessions")
    def session(body: SessionBody):
        return {"session_id": runtime.repository.create_demo_session(body.employee_id), "mode": "demo_identity_selection"}

    @app.post("/cases")
    def create_case(authorization: str | None = Header(default=None)):
        return runtime.repository.create_case(token(authorization), runtime.clock).model_dump(mode="json", exclude={"session_id"})

    @app.get("/cases/{case_id}")
    def get_case(case_id: str, authorization: str | None = Header(default=None)):
        ctx = context(case_id, authorization)
        case = runtime.repository.get_case(ctx)
        handoff = None
        if case.handoff_id:
            import json
            with runtime.repository.transaction() as db:
                item = json.loads(db.execute("SELECT payload FROM handoffs WHERE record_id=?", (case.handoff_id,)).fetchone()[0])
                handoff = {k: item[k] for k in ["handoff_id", "status", "support_group", "acknowledged_at"]}
        evidence = runtime.repository.evidence(ctx)
        messages = [{**m.model_dump(mode="json"), **(present_answer(m.text, evidence) if m.role == "assistant" else {"citations": []})} for m in runtime.repository.messages(ctx)]
        public_case = case.model_dump(mode="json", exclude={"session_id"})
        if pending := public_case["facts"].get("pending_consent"):
            pending["explanation"] = present_answer(pending["explanation"], evidence)["text"]
        return {"case": public_case, "messages": messages, "sources": source_catalog(evidence)[0], "evidence": [{"evidence_id": e.evidence_id, "source": e.source.model_dump(mode="json"), "tool_name": e.tool_name} for e in evidence], "handoff": handoff}

    @app.get("/cases/{case_id}/activity")
    def case_activity(case_id: str, after: int = Query(default=0, ge=0), authorization: str | None = Header(default=None)):
        ctx = context(case_id, authorization)
        events = runtime.repository.events(ctx, after)
        return {"events": [item for event in events if (item := activity(event)) is not None],
                "cursor": events[-1]["sequence"] if events else after, "has_more": len(events) == 200}

    @app.get("/cases/{case_id}/diagnostics")
    def case_diagnostics(case_id: str, after: int = Query(default=0, ge=0), authorization: str | None = Header(default=None)):
        # Same ownership boundary as the case; this is a local demo inspector,
        # not a production developer role or an authorization bypass.
        ctx = context(case_id, authorization)
        events = runtime.repository.events(ctx, after)
        return {"events": events, "cursor": events[-1]["sequence"] if events else after, "has_more": len(events) == 200}

    @app.post("/cases/{case_id}/messages")
    def message(case_id: str, body: MessageBody, authorization: str | None = Header(default=None)):
        return runtime.agent.turn(context(case_id, authorization), body.text)

    @app.post("/cases/{case_id}/consent")
    def consent(case_id: str, body: ConsentBody, authorization: str | None = Header(default=None)):
        ctx = context(case_id, authorization)
        runtime.resolution.consent(ctx, body.operation, body.allow)
        return {"status": "recorded", "operation": body.operation, "allowed": body.allow}

    @app.post("/cases/{case_id}/feedback")
    def feedback(case_id: str, body: FeedbackBody, authorization: str | None = Header(default=None)):
        return runtime.feedback(context(case_id, authorization), body.resolved)

    @app.get("/review/approvals")
    def approvals(authorization: str | None = Header(default=None)):
        rows = runtime.approvals.pending(token(authorization), runtime.clock)
        result = []
        import json
        with runtime.repository.transaction() as db:
            for row in rows:
                proposal = json.loads(db.execute("SELECT payload FROM proposals WHERE record_id=?", (row.proposal_id,)).fetchone()[0])
                result.append({"approval": row.model_dump(mode="json"), "action": proposal["action"]})
        return result

    @app.post("/review/approvals/{approval_id}/decision")
    def decision(approval_id: str, body: DecisionBody, authorization: str | None = Header(default=None)):
        return runtime.reviewer_decision(token(authorization), approval_id, body.approve)

    @app.get("/review/handoffs")
    def handoffs(authorization: str | None = Header(default=None)):
        return runtime.handoffs.queue(token(authorization))

    @app.post("/review/handoffs/{handoff_id}/acknowledge")
    def acknowledge(handoff_id: str, authorization: str | None = Header(default=None)):
        return runtime.handoffs.acknowledge(token(authorization), handoff_id, runtime.clock)

    if ui_dir:
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    return app
