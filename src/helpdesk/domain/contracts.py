"""Validated contracts shared by repositories, tools, and workflow nodes."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


def new_id(prefix: str) -> str:
    from uuid import uuid4
    return f"{prefix}-{uuid4().hex}"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Contract):
    source_id: str
    source_type: str
    version: str
    observed_at: AwareDatetime | None = None


class ToolError(Contract):
    code: str
    message: str
    retryable: bool = False


class ToolResult(Contract):
    tool_call_id: str
    status: Literal["success", "not_found", "denied", "error"]
    data: Any = None
    sources: list[Source] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    retrieved_at: AwareDatetime
    error: ToolError | None = None

    @model_validator(mode="after")
    def consistent_result(self):
        if self.status == "success" and (self.error is not None or self.data is None):
            raise ValueError("Successful tools require data and no error")
        if self.status != "success" and (self.error is None or self.data is not None):
            raise ValueError("Unsuccessful tools require explicit error and no data")
        return self


class Message(Contract):
    message_id: str = Field(default_factory=lambda: new_id("MSG"))
    case_id: str
    employee_id: str
    role: Literal["employee", "assistant"]
    text: str = Field(min_length=1, max_length=12000)
    created_at: AwareDatetime


class VerificationResult(Contract):
    outcome: Literal["success", "failure", "unknown"]
    method: str
    observations: dict[str, Any] = Field(default_factory=dict)
    employee_confirmation_required: bool = False
    employee_confirmed: bool = False


CaseStatus = Literal["investigating", "awaiting_employee", "awaiting_approval", "awaiting_verification", "resolved", "escalated"]


class Case(Contract):
    case_id: str = Field(default_factory=lambda: new_id("CASE"))
    session_id: str
    employee_id: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    version: int = Field(default=0, ge=0)
    status: CaseStatus = "investigating"
    facts: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    attempted_fixes: list[dict[str, Any]] = Field(default_factory=list)
    tool_errors: list[dict[str, Any]] = Field(default_factory=list)
    verification: VerificationResult | None = None
    handoff_id: str | None = None
    investigation_steps: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def resolution_requires_observation(self):
        if self.updated_at < self.created_at:
            raise ValueError("Case update precedes creation")
        if self.status == "resolved":
            v = self.verification
            if v is None or v.outcome != "success":
                raise ValueError("Resolution requires successful verification")
            if v.employee_confirmation_required and not v.employee_confirmed:
                raise ValueError("Resolution requires employee confirmation")
        if self.status == "escalated" and not self.handoff_id:
            raise ValueError("Escalation requires a durable handoff reference")
        return self


class EvidenceRecord(Contract):
    evidence_id: str = Field(default_factory=lambda: new_id("EVID"))
    case_id: str
    employee_id: str
    tool_name: str
    tool_call_id: str
    source: Source
    facts: Any
    retrieved_at: AwareDatetime


class PolicyDecision(Contract):
    decision: Literal["allow", "deny", "approval_required"]
    rule_ids: list[str]
    policy_version: str
    reason: str
    approver_role: str | None = None
    verification_requirements: list[str] = Field(default_factory=list)


class ActionRequest(Contract):
    operation: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=30)
    parameters: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class Proposal(Contract):
    proposal_id: str = Field(default_factory=lambda: new_id("PROP"))
    case_id: str
    employee_id: str
    action: ActionRequest
    decision: PolicyDecision
    scope_hash: str
    created_at: AwareDatetime


class Approval(Contract):
    approval_id: str = Field(default_factory=lambda: new_id("APPR"))
    proposal_id: str
    case_id: str
    employee_id: str
    approver_id: str
    scope_hash: str
    policy_version: str
    created_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    decided_by: str | None = None
    decided_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_decision(self):
        if self.expires_at <= self.created_at:
            raise ValueError("Approval expiry must follow creation")
        if self.status in {"approved", "rejected"}:
            if not self.decided_by or self.decided_at is None:
                raise ValueError("Decision needs an attributed reviewer and timestamp")
            if self.decided_by != self.approver_id or not self.created_at <= self.decided_at < self.expires_at:
                raise ValueError("Decision is out of scope or expired")
        return self
