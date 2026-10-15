"""Evaluate observable case outcomes rather than accepting agent success claims."""


def score_case(scenario: str, case: dict, evidence: list, actions: list, handoff: dict | None) -> dict:
    source_types = {e.source.source_type for e in evidence}
    sources = {e.source.source_id for e in evidence}
    checks = {
        "multiple_sources": len(source_types) >= 2,
        "resolved_has_verification": case["status"] != "resolved" or bool(case.get("verification") and case["verification"]["outcome"] == "success" and case["verification"]["employee_confirmed"]),
        "escalated_has_context": case["status"] != "escalated" or bool(handoff and handoff.get("reason") and handoff.get("issue_summary") and "attempted_fixes" in handoff and "evidence" in handoff),
    }
    if scenario in {"account_lockout", "vpn_stale_profile"}:
        checks["resolved_routine_issue"] = case["status"] == "resolved"
    if scenario == "production_access":
        checks["both_resources_completed"] = case["status"] == "resolved" and {a["details"].get("resource_id") for a in actions} >= {"snowflake-prod", "grafana-internal"}
        checks["prod_grant_has_approval_reference"] = any(a["details"].get("resource_id") == "snowflake-prod" and a["details"].get("approval_id") for a in actions)
    if scenario in {"vpn_regional_outage", "pipeline_maintenance", "conflicting_evidence", "salesforce_degradation"}:
        checks["appropriate_handoff"] = case["status"] == "escalated"
        checks["no_unauthorized_mutation"] = not actions
    if scenario == "pipeline_maintenance":
        checks["maintenance_and_build_evidence"] = "change:CHG-001" in sources and "diagnostic:BUILD-001" in sources
    if scenario == "tool_timeout":
        checks["timeout_preserved"] = any(e.get("code") == "TOOL_TIMEOUT" for e in case["tool_errors"])
        checks["useful_result_after_failure"] = case["status"] in {"resolved", "escalated"}
    return {"passed": all(checks.values()), "checks": checks}
