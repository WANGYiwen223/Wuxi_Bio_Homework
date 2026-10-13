"""Bounded LangGraph tool loop with durable per-case dialogue checkpoints."""

import json
import sqlite3
import threading
import time
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import Field, ValidationError

from helpdesk.domain.contracts import ActionRequest, new_id
from helpdesk.domain.lifecycle import transition
from helpdesk.models.client import ModelFailure
from helpdesk.observability.redaction import redact
from helpdesk.observability.presentation import TOOL_LABELS, present_answer
from helpdesk.tools.read_tools import Args
from helpdesk.workflow.prompts import SYSTEM_PROMPT


class FinishArgs(Args):
    kind: Literal["clarify", "guidance"]
    message: str = Field(min_length=1, max_length=6000)
    missing_information: list[str] = Field(default_factory=list, max_length=2)


class HandoffArgs(Args):
    reason: str = Field(min_length=1, max_length=1000)


class ConsentArgs(Args):
    operation: Literal["unlock_demo_account", "refresh_demo_vpn_profile", "grant_demo_access"]
    explanation: str = Field(min_length=1, max_length=1000)


class RequirementsArgs(Args):
    resource_ids: list[Literal["snowflake-prod", "snowflake-dev", "grafana-internal"]] = Field(default_factory=list, max_length=3)
    impact: str = Field(default="Not yet confirmed", max_length=1000)


class ActionParameters(Args):
    device_id: str | None = Field(default=None, description="Only for refresh_demo_vpn_profile: assigned DEV-* identifier")
    role: Literal["reader", "viewer"] | None = Field(default=None, description="Only for grant_demo_access")
    business_justification: str | None = Field(default=None, max_length=1000, description="Business justification for access; required for PROD")


class ProposeArgs(Args):
    operation: Literal["unlock_demo_account", "refresh_demo_vpn_profile", "grant_demo_access"]
    resource_id: Literal["okta", "vpn", "snowflake-prod", "snowflake-dev", "grafana-internal"] = Field(description="Service ID okta/vpn for account/profile actions, never employee/account/device ID")
    environment: Literal["INTERNAL", "PROD", "DEV"] = Field(description="INTERNAL for okta/vpn/grafana; PROD for snowflake-prod")
    parameters: ActionParameters = Field(default_factory=ActionParameters)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class LoopState(TypedDict, total=False):
    turn_id: str
    dialogue: list[dict]
    model_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    last_calls: list[dict]
    final: str
    stop: bool
    failure: str
    duplicate_calls: int
    signatures: list[str]
    fingerprints: dict[str, str]


EXTRA_TOOLS = {
    "finish_turn": (FinishArgs, "End the turn with a focused question or evidence-based guidance. Cannot mark a case resolved."),
    "request_consent": (ConsentArgs, "Ask for explicit employee consent through the UI before proposing a self-service action."),
    "propose_action": (ProposeArgs, "Propose a scoped mock action. unlock: resource_id=okta, environment=INTERNAL, parameters={}. VPN refresh: resource_id=vpn, environment=INTERNAL, parameters={device_id: assigned DEV-* ID}. Grant: resource_id=snowflake-prod/grafana-internal, parameters={role: reader/viewer, business_justification: reason}. NEVER include employee_id, consent or authorization facts. Backend policy decides."),
    "request_handoff": (HandoffArgs, "Create an evidence-preserving handoff to human IT. Do not claim human acknowledgement."),
    "record_case_requirements": (RequirementsArgs, "Record every requested resource for a multi-resource access issue before proposing grants. These facts never authorize execution."),
}


class DiagnosticAgent:
    def __init__(self, repository, read_tools, model, settings, checkpoint_path, action_handler=None, handoff_handler=None):
        self.repository, self.tools, self.model, self.settings = repository, read_tools, model, settings
        self.action_handler, self.handoff_handler = action_handler, handoff_handler
        self._lock = threading.RLock()  # One local worker; protects checkpoint writes and case turns.
        self._connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self._connection)
        self.checkpointer.setup()

    def close(self):
        self._connection.close()

    def _schemas(self):
        return self.tools.schemas() + [{"name": n, "description": d, "parameters": m.model_json_schema()} for n, (m, d) in EXTRA_TOOLS.items()]

    def _model_node(self, state, context):
        if state["model_calls"] >= self.settings.max_model_calls or state["tool_calls"] >= self.settings.max_tool_calls or state.get("duplicate_calls", 0) >= 2:
            return {"stop": True, "failure": "investigation_budget", "final": "I could not complete the investigation within its limits. I will preserve the findings for IT."}
        case = self.repository.get_case(context)
        public = case.model_dump(mode="json", exclude={"session_id"})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "system", "content": json.dumps({"clock": context.clock.now().isoformat(), "case": public})}, *state["dialogue"]]
        if len(json.dumps(messages)) > self.settings.max_context_chars:
            return {"stop": True, "failure": "context_budget", "final": "The investigation reached its context limit. I will preserve the findings for IT."}
        started = time.monotonic()
        call_id = new_id("MODEL")
        trace = {"turn_id": state["turn_id"], "call_id": call_id, "model_call": state["model_calls"] + 1}
        self.repository.trace(context, "model_started", trace)
        try:
            reply = self.model.respond(messages, self._schemas())
        except ModelFailure as error:
            self.repository.trace(context, "model_failure", {**trace, "error_type": error.category, "duration_ms": round((time.monotonic() - started) * 1000)})
            latest = self.repository.get_case(context)
            self.repository.save_case(context, transition(latest, latest.status, context.clock.now(), tool_errors=[*latest.tool_errors, {"tool_name": "model", "code": error.category}]))
            return {"model_calls": state["model_calls"] + 1, "stop": True, "failure": "model_unavailable", "final": "The model service is unavailable. I will preserve the investigation for IT."}
        self.repository.trace(context, "model_call", {**trace, "duration_ms": round((time.monotonic() - started) * 1000), "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens})
        calls = [c.model_dump() for c in reply.calls]
        assistant = {"role": "assistant", "content": redact(reply.text) or None}
        if calls:
            assistant["tool_calls"] = [{"id": c["call_id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls]
        updates = {"dialogue": [*state["dialogue"], assistant], "last_calls": calls, "model_calls": state["model_calls"] + 1, "input_tokens": state["input_tokens"] + reply.input_tokens, "output_tokens": state["output_tokens"] + reply.output_tokens}
        if not calls:
            # Free text can clarify, but never changes resolution status.
            updates.update(stop=True, final=redact(reply.text) or "Please describe the affected application and error.")
        return updates

    def _tool_node(self, state, context):
        dialogue = list(state["dialogue"])
        signatures = list(state.get("signatures", []))
        stop, final, failure = False, "", ""
        duplicates = state.get("duplicate_calls", 0)
        fingerprints = dict(state.get("fingerprints", {}))
        executed = 0
        for call in state["last_calls"]:
            name = call["name"]
            started = time.monotonic()
            trace = {"turn_id": state["turn_id"], "call_id": call["call_id"], "tool_name": name if name in TOOL_LABELS else "unknown_tool"}
            if stop or state["tool_calls"] + executed >= self.settings.max_tool_calls:
                output = {"status": "denied", "reason": "Turn already stopped or tool budget exhausted"}
                trace["skipped"] = True
            else:
                self.repository.trace(context, "tool_started", trace)
                executed += 1
                try:
                    args = json.loads(call["arguments"])
                    signature = json.dumps([name, args], sort_keys=True)
                    signatures.append(signature)
                    if name in EXTRA_TOOLS:
                        parsed = EXTRA_TOOLS[name][0].model_validate(args)
                        if name == "finish_turn":
                            final, stop = redact(parsed.message), True
                            case = self.repository.get_case(context)
                            self.repository.save_case(context, transition(case, "awaiting_employee", context.clock.now(), missing_information=parsed.missing_information, facts={**case.facts, "last_response_kind": parsed.kind}))
                            output = {"status": "success", "case_status": "awaiting_employee"}
                        elif name == "request_consent":
                            case = self.repository.get_case(context)
                            self.repository.save_case(context, transition(case, "awaiting_employee", context.clock.now(), facts={**case.facts, "pending_consent": {"operation": parsed.operation, "explanation": redact(parsed.explanation)}}))
                            final, stop = f"{redact(parsed.explanation)}\nPlease use the permission buttons below to continue or decline.", True
                            output = {"status": "awaiting_employee_consent", "operation": parsed.operation}
                        elif name == "propose_action" and self.action_handler:
                            request = ActionRequest(**{**parsed.model_dump(), "parameters": parsed.parameters.model_dump(exclude_none=True)})
                            output = self.action_handler(context, request, call["call_id"])
                            if output.get("stop"):
                                stop, final = True, output["message"]
                        elif name == "request_handoff" and self.handoff_handler:
                            output = self.handoff_handler(context, redact(parsed.reason))
                            final, stop = output["message"], True
                        elif name == "record_case_requirements":
                            case = self.repository.get_case(context)
                            resources = sorted(set(case.facts.get("required_resources", [])) | set(parsed.resource_ids))
                            self.repository.save_case(context, transition(case, case.status, context.clock.now(), facts={**case.facts, "required_resources": resources, "impact": redact(parsed.impact)}))
                            output = {"status": "success", "required_resources": resources}
                        else:
                            output = {"status": "denied", "reason": "Handler not enabled"}
                    else:
                        result = self.tools.call(context, name, args)
                        output = result.model_dump(mode="json")
                        fingerprint = json.dumps({"status": result.status, "data": result.data, "sources": [s.model_dump(mode="json") for s in result.sources], "error_code": result.error.code if result.error else None}, sort_keys=True)
                        duplicates = duplicates + 1 if fingerprints.get(signature) == fingerprint else 0
                        fingerprints[signature] = fingerprint
                        if result.status != "success":
                            case = self.repository.get_case(context)
                            self.repository.save_case(context, transition(case, case.status, context.clock.now(), tool_errors=[*case.tool_errors, {"tool_name": name, "code": result.error.code}]))
                except (ValueError, ValidationError):
                    output = {"status": "error", "error": {"code": "INVALID_ARGUMENTS", "retryable": False}}
            self.repository.trace(context, "tool_completed", {
                **trace, "status": "skipped" if trace.get("skipped") else output.get("status", "unknown"),
                "duration_ms": round((time.monotonic() - started) * 1000),
                "error_code": (output.get("error") or {}).get("code"),
                "evidence_ids": output.get("evidence_ids", []),
                "read_call_id": output.get("tool_call_id"),
            })
            dialogue.append({"role": "tool", "tool_call_id": call["call_id"], "content": json.dumps(output, ensure_ascii=False)})
        return {"dialogue": dialogue, "tool_calls": state["tool_calls"] + executed, "signatures": signatures, "fingerprints": fingerprints, "duplicate_calls": duplicates, "stop": stop, "final": final, "failure": failure}

    def _reconcile_dialogue(self, context, dialogue):
        """Close interrupted tool exchanges without replaying side effects."""
        repaired = []
        for index, message in enumerate(dialogue):
            repaired.append(message)
            calls = message.get("tool_calls", []) if message.get("role") == "assistant" else []
            if not calls:
                continue
            following = []
            for later in dialogue[index + 1:]:
                if later.get("role") != "tool":
                    break
                following.append(later.get("tool_call_id"))
            for call in calls:
                if call["id"] in following:
                    continue
                output = {"status": "interrupted", "reason": "No completed tool result recorded; re-read current evidence before continuing."}
                if call["function"]["name"] == "propose_action":
                    with self.repository.transaction() as db:
                        self.repository._owned_case(db, context)
                        row = db.execute("SELECT proposal_id FROM proposal_receipts WHERE request_key=?", (f"{context.case_id}:{call['id']}",)).fetchone()
                        if row:
                            action = db.execute("SELECT payload FROM actions WHERE json_extract(payload,'$.proposal_id')=?", (row[0],)).fetchone()
                            approval = db.execute("SELECT payload FROM approvals WHERE json_extract(payload,'$.proposal_id')=?", (row[0],)).fetchone()
                            output = json.loads(action[0]) if action else {"status": "proposal_recorded", "proposal_id": row[0], "approval_status": json.loads(approval[0])["status"] if approval else None}
                repaired.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(output)})
        return repaired

    def turn(self, context, text):
        with self._lock:
            case = self.repository.get_case(context)
            if case.status in {"resolved", "escalated", "awaiting_approval"}:
                raise ValueError("This case is closed or waiting for reviewer approval")
            if case.status == "awaiting_verification":
                raise ValueError("Submit fix feedback before continuing diagnosis")
            turn_id = new_id("TURN")
            self.repository.trace(context, "turn_started", {"turn_id": turn_id})
            try:
                return self._turn(context, text, turn_id)
            except Exception as error:
                self.repository.trace(context, "turn_failed", {"turn_id": turn_id, "error_type": type(error).__name__})
                raise

    def _turn(self, context, text, turn_id):
        with self._lock:
            started = time.monotonic()
            case = self.repository.get_case(context)
            if case.status != "investigating":
                self.repository.save_case(context, transition(case, "investigating", context.clock.now()))
            safe_text = redact(text)
            self.repository.append_message(context, "employee", safe_text)
            builder = StateGraph(LoopState)
            builder.add_node("model", lambda state: self._model_node(state, context))
            builder.add_node("tools", lambda state: self._tool_node(state, context))
            builder.add_edge(START, "model")
            builder.add_conditional_edges("model", lambda s: END if s.get("stop") else "tools")
            builder.add_conditional_edges("tools", lambda s: END if s.get("stop") else "model")
            graph = builder.compile(checkpointer=self.checkpointer)
            config = {"configurable": {"thread_id": context.case_id}, "recursion_limit": 2 * self.settings.max_model_calls + 5}
            previous = graph.get_state(config).values
            dialogue = list(previous.get("dialogue", []))
            if not dialogue:
                # Recover conversation if a checkpoint file was lost; business state survives.
                dialogue = [{"role": "user" if m.role == "employee" else "assistant", "content": m.text} for m in self.repository.messages(context)[:-1]]
            dialogue = self._reconcile_dialogue(context, dialogue)
            initial = {"turn_id": turn_id, "dialogue": [*dialogue, {"role": "user", "content": safe_text}], "model_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "stop": False, "final": "", "failure": "", "signatures": [], "fingerprints": {}, "duplicate_calls": 0}
            state = graph.invoke(initial, config)
            if state.get("failure") and self.handoff_handler:
                state["final"] = self.handoff_handler(context, state["failure"])["message"]
            else:
                current = self.repository.get_case(context)
                if current.status == "investigating":
                    self.repository.save_case(context, transition(current, "awaiting_employee", context.clock.now()))
            self.repository.append_message(context, "assistant", state["final"])
            metrics = {k: state[k] for k in ["model_calls", "tool_calls", "input_tokens", "output_tokens"]}
            metrics["duration_ms"] = round((time.monotonic() - started) * 1000)
            current = self.repository.get_case(context)
            self.repository.trace(context, "turn_completed", {**metrics, "turn_id": turn_id, "case_status": current.status, "failure": state.get("failure") or None})
            answer = present_answer(state["final"], self.repository.evidence(context))
            return {"message": answer["text"], "citations": answer["citations"], "case": current.model_dump(mode="json", exclude={"session_id"}), "metrics": metrics, "failure": state.get("failure") or None}
