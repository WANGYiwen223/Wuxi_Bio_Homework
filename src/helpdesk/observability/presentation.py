"""Employee-facing projections of durable evidence and execution events."""

import json
import re

from helpdesk.observability.redaction import redact


TOOL_LABELS = {
    "get_employee_context": "Check your account and assigned devices",
    "search_knowledge": "Search support documentation",
    "get_runbook": "Read the relevant support procedure",
    "get_service_status": "Check service health and incidents",
    "get_recent_changes": "Check recent system changes",
    "get_diagnostic_snapshot": "Read current diagnostic observations",
    "search_resolution_history": "Compare previous resolutions",
    "propose_action": "Check authorization and request a fix",
    "request_consent": "Request your permission",
    "request_handoff": "Prepare the handoff to IT",
    "record_case_requirements": "Record the scope of your request",
    "finish_turn": "Prepare findings and next steps",
}

SOURCE_LABELS = {
    "employee": "Employee directory", "device": "Assigned device", "resource": "Shared resource access",
    "account": "Account state", "access_grant": "Access record",
    "knowledge": "Support procedure", "system_status": "Service health",
    "incident": "Service incident", "change": "System change",
    "diagnostic": "Diagnostic observation", "history": "Previous resolution",
}


def source_catalog(evidence):
    """Stable case-local numbers, deduplicated only for the same source snapshot."""
    sources, references, snapshots = [], {}, {}
    for item in evidence:
        key = (item.source.source_id, item.source.version, item.source.observed_at,
               json.dumps(item.facts, sort_keys=True, ensure_ascii=False))
        if key not in snapshots:
            number = len(sources) + 1
            facts = item.facts if isinstance(item.facts, dict) else {}
            label = SOURCE_LABELS.get(item.source.source_type, "Investigation source")
            title = facts.get("title") or label
            service = facts.get("service_id")
            if service:
                title = f"{str(service).upper()} · {title}"
            summary = "; ".join(f"{k.replace('_', ' ')}: {facts[k]}" for k in
                                ("health", "status", "region", "applicability", "symptoms", "root_cause")
                                if k in facts)
            sources.append({"number": number, "title": redact(str(title)),
                            "type": label, "summary": redact(summary),
                            "observed_at": item.source.observed_at.isoformat() if item.source.observed_at else None,
                            "version": item.source.version})
            snapshots[key] = number
        references[item.evidence_id] = snapshots[key]
        # Older conversations may cite source IDs instead of evidence IDs.
        references.setdefault(item.source.source_id, snapshots[key])
    return sources, references


def present_answer(value, evidence):
    sources, references = source_catalog(evidence)
    cited = set()

    def replace(match):
        key = match.group(0).strip("[]`")
        number = references.get(key)
        if number is None:
            return "[source unavailable]"
        cited.add(number)
        return f"[{number}]"

    # Tolerate plain, backtick, single-bracket and double-bracket references.
    value = re.sub(r"(?:\[\[|\[|`)?EVID-[A-Za-z0-9_-]+(?:\]\]|\]|`)?", replace, redact(value))
    for key in sorted((k for k in references if not k.startswith("EVID-")), key=len, reverse=True):
        value = re.sub(r"(?<![\w:-])" + re.escape(key) + r"(?![\w:-])", replace, value)
    # Other opaque workflow IDs are useful in diagnostics, not employee prose.
    value = re.sub(r"\b(?:APPR|PROP|HANDOFF|ACTION|CASE|CALL|TRACE)-[0-9a-f]{32}\b", "internal record", value)
    return {"text": value, "citations": [s for s in sources if s["number"] in cited]}


def activity(event):
    """Allowlisted facts about execution, never model reasoning or raw payloads."""
    kind = event["event"]
    status = "completed"
    if kind == "turn_started":
        label, status = "Investigation started", "running"
    elif kind == "model_started":
        label, status = "Reviewing the request and available findings", "running"
    elif kind == "model_call":
        label = "Next step prepared"
        if event.get("response_error"):
            label, status = "Model did not return a complete, usable response", "error"
    elif kind == "model_response_retry":
        label, status = "Retrying the response with the investigation context preserved", "running"
    elif kind == "model_failure":
        label, status = "Model service unavailable; preserving findings", "error"
        if event.get("error_type") in {"model_empty_response", "model_output_truncated", "model_response_refused"}:
            label = "Unable to produce a usable response; preserving findings for IT"
    elif kind in {"tool_started", "tool_completed"}:
        label = TOOL_LABELS.get(event.get("tool_name"), "Run a diagnostic step")
        result = event.get("status")
        status = "running" if kind == "tool_started" else "error" if result == "error" else "unavailable" if result in {"denied", "not_found"} else "skipped" if result == "skipped" else "completed"
        if kind == "tool_completed" and result in {"denied", "not_found", "error", "skipped"}:
            label += {"denied": " — not permitted", "not_found": " — no matching data", "error": " — could not complete", "skipped": " — skipped"}[result]
    elif kind == "turn_completed":
        label = {
            "awaiting_employee": "Waiting for your reply or permission",
            "awaiting_approval": "Waiting for manager approval",
            "awaiting_verification": "Waiting for your feedback on the fix",
            "escalated": "Investigation handed to IT",
            "resolved": "Issue resolved",
        }.get(event.get("case_status"), "Investigation step finished")
    elif kind == "turn_failed":
        label, status = "Investigation interrupted; reload the case before continuing", "error"
    elif kind == "action_proposed":
        label = {"allow": "Fix authorized", "deny": "Fix not permitted", "approval_required": "Manager approval required"}.get(event.get("decision"), "Authorization checked")
    elif kind == "action_executed":
        label = "Simulated fix executed; outcome needs verification"
    elif kind == "action_refused":
        label, status = "Fix refused by the authorization check", "unavailable"
    elif kind == "employee_consent":
        label = "Permission recorded" if event.get("allowed") else "Permission declined"
    elif kind == "approval_decided":
        label = "Manager review: " + event.get("status", "recorded")
    elif kind == "outcome_verified":
        label = "Outcome checked: " + event.get("outcome", "unknown")
    elif kind == "handoff_created":
        label = "Case queued for IT with investigation context"
    elif kind == "handoff_acknowledged":
        label = "An IT specialist acknowledged the case"
    else:
        return None
    return {"sequence": event["sequence"], "event": kind, "label": label, "status": status,
            "turn_id": event.get("turn_id"), "call_id": event.get("call_id"),
            "recorded_at": event.get("recorded_at", event.get("created_at")),
            "duration_ms": event.get("duration_ms")}
