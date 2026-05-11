"""Pydantic schemas for OpsFlow AI.

These models are the contract between the rule engine, LLM assist layer,
decision layer, review queue, and evaluation scripts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RequestType(StrEnum):
    """Supported work request types."""

    BUG_REPORT = "bug_report"
    DATA_REQUEST = "data_request"
    CUSTOMER_SUPPORT = "customer_support"
    FEATURE_REQUEST = "feature_request"
    APPROVAL_REQUEST = "approval_request"
    INTERNAL_OPS = "internal_ops"
    OTHER = "other"


class Team(StrEnum):
    """Known owner teams."""

    ENGINEERING = "engineering"
    DATA = "data"
    PRODUCT = "product"
    CS = "cs"
    OPS = "ops"
    UNASSIGNED = "unassigned"


class Priority(StrEnum):
    """Request priority."""

    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(StrEnum):
    """Risk level used by automation policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AutomationDecision(StrEnum):
    """Final automation decision."""

    READY_FOR_APPROVAL = "ready_for_approval"
    DRAFT_ONLY = "draft_only"
    REVIEW_REQUIRED = "review_required"
    REJECT = "reject"


class ReviewAction(StrEnum):
    """Actions a reviewer can take for a review queue item."""

    ASK_CLARIFICATION = "ask_clarification"
    ROUTE_TO_OWNER = "route_to_owner"
    SECURITY_REVIEW = "security_review"
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    HOLD = "hold"


class ProcessingStatus(StrEnum):
    """Per-request processing status."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class CandidateBase(BaseModel):
    """Shared fields for scored candidates."""

    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None


class RequestTypeCandidate(CandidateBase):
    """Candidate request type with matched evidence."""

    type: RequestType
    matched_signals: list[str] = Field(default_factory=list)


class TeamCandidate(CandidateBase):
    """Candidate target team with matched evidence."""

    team: Team
    matched_signals: list[str] = Field(default_factory=list)


class ExtractedFields(BaseModel):
    """Fields extracted from a raw request.

    The model keeps common fields explicit while allowing request-type-specific
    fields through ``extra`` so the rule engine can evolve without a migration.
    """

    model_config = ConfigDict(extra="allow")

    symptom: str | None = None
    affected_customer_or_user: str | None = None
    impact_scope: str | None = None
    reproduction_steps: str | None = None
    first_seen_at: str | None = None
    environment: str | None = None
    dataset_or_metric: str | None = None
    purpose: str | None = None
    deadline: str | None = None
    format: str | None = None
    delivery_channel: str | None = None
    refresh_frequency: str | None = None
    user_need: str | None = None
    expected_outcome: str | None = None
    priority_reason: str | None = None
    target_release: str | None = None
    customer: str | None = None
    issue_detail: str | None = None
    required_action: str | None = None
    contact_channel: str | None = None
    approval_target: str | None = None
    scope_or_amount: str | None = None
    approval_owner: str | None = None
    policy_reference: str | None = None
    requested_action: str | None = None
    target_user_or_system: str | None = None


class RawRequest(BaseModel):
    """Input request after loading from CSV, JSONL, or Slack-style JSON."""

    request_id: str
    raw_text: str = Field(min_length=1)
    requester: str | None = None
    channel: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedRequest(BaseModel):
    """Standard normalized request schema."""

    schema_version: str = "normalized_request.v1"
    rule_config_version: str
    scoring_policy_version: str
    risk_policy_version: str
    privacy_policy_version: str
    request_id: str
    raw_text: str = Field(min_length=1)
    masked_text: str | None = None
    request_type: RequestType
    request_type_confidence: float = Field(ge=0.0, le=1.0)
    request_type_candidates: list[RequestTypeCandidate] = Field(min_length=1)
    summary: str
    required_action: str | None = None
    target_team: Team
    target_team_confidence: float = Field(ge=0.0, le=1.0)
    target_team_candidates: list[TeamCandidate] = Field(min_length=1)
    priority: Priority
    risk_level: RiskLevel
    pii_detected: bool = False
    pii_types: list[str] = Field(default_factory=list)
    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)
    missing_fields: list[str] = Field(default_factory=list)
    needs_review: bool
    review_reason: str | None = None
    decision_reasons: list[str] = Field(default_factory=list)
    llm_used: bool = False
    model_name: str | None = None
    suggested_ticket_title: str | None = None
    suggested_ticket_body: str | None = None
    automation_decision: AutomationDecision
    processing_status: ProcessingStatus = ProcessingStatus.SUCCEEDED
    errors: list[str] = Field(default_factory=list)

    @field_validator("missing_fields", "decision_reasons", "pii_types")
    @classmethod
    def _deduplicate_strings(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def _validate_top_candidate_mirrors(self) -> NormalizedRequest:
        top_type = self.request_type_candidates[0]
        if self.request_type != top_type.type:
            raise ValueError("request_type must match request_type_candidates[0].type")
        if self.request_type_confidence != top_type.confidence:
            raise ValueError(
                "request_type_confidence must match request_type_candidates[0].confidence"
            )

        top_team = self.target_team_candidates[0]
        if self.target_team != top_team.team:
            raise ValueError("target_team must match target_team_candidates[0].team")
        if self.target_team_confidence != top_team.confidence:
            raise ValueError(
                "target_team_confidence must match target_team_candidates[0].confidence"
            )
        return self

    @model_validator(mode="after")
    def _validate_decision_invariants(self) -> NormalizedRequest:
        if self.automation_decision == AutomationDecision.READY_FOR_APPROVAL:
            if self.missing_fields:
                raise ValueError("ready_for_approval requires no missing_fields")
            if self.risk_level == RiskLevel.HIGH:
                raise ValueError("ready_for_approval cannot be high risk")
            if self.request_type == RequestType.OTHER:
                raise ValueError("other request_type cannot be ready_for_approval")

        if self.pii_detected and not self.masked_text:
            raise ValueError("pii_detected requests must include masked_text")

        if self.needs_review and not self.review_reason:
            raise ValueError("needs_review requests must include review_reason")

        return self


class TicketDraft(BaseModel):
    """Ticket draft generated from a normalized request."""

    request_id: str
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    labels: list[str] = Field(default_factory=list)
    assignee_team: Team
    priority: Priority
    source_decision: AutomationDecision

    @model_validator(mode="after")
    def _validate_ticket_source_decision(self) -> TicketDraft:
        if self.source_decision == AutomationDecision.REJECT:
            raise ValueError("rejected requests should not produce ticket drafts")
        return self


class ReviewQueueItem(BaseModel):
    """Item presented to a human reviewer."""

    request_id: str
    raw_text: str = Field(min_length=1)
    masked_text: str | None = None
    suggested_type: RequestType
    suggested_team: Team
    type_candidates: list[RequestType] = Field(default_factory=list)
    team_candidates: list[Team] = Field(default_factory=list)
    priority: Priority
    risk_level: RiskLevel
    review_reason: str = Field(min_length=1)
    suggested_question: str | None = None
    decision_reasons: list[str] = Field(default_factory=list)
    review_action: ReviewAction
    pii_detected: bool = False


class RuleMatch(BaseModel):
    """A rule match recorded in execution trace."""

    rule_id: str
    matched_keyword: str | None = None
    suggested_type: RequestType | None = None
    suggested_team: Team | None = None
    weight: float | None = Field(default=None, ge=0.0)


class RiskEval(BaseModel):
    """Risk evaluation trace."""

    risk_level: RiskLevel
    matched_rules: list[str] = Field(default_factory=list)


class EvaluatedDecision(BaseModel):
    """One step in the decision cascade."""

    step: AutomationDecision
    matched: bool
    trigger: str | None = None


class LlmAssistTrace(BaseModel):
    """Trace of optional LLM assistance."""

    used: bool = False
    reason: str | None = None
    model_name: str | None = None
    suggested_clarification: str | None = None
    error: str | None = None


class FinalDecisionTrace(BaseModel):
    """Final decision portion of execution trace."""

    automation_decision: AutomationDecision
    decision_reasons: list[str] = Field(default_factory=list)
    review_reason: str | None = None


class ExecutionTrace(BaseModel):
    """Trace for debugging, evaluation, and reproducibility."""

    request_id: str
    original_text: str
    schema_version: str = "normalized_request.v1"
    rule_config_version: str
    scoring_policy_version: str
    risk_policy_version: str
    privacy_policy_version: str
    rule_matches: list[RuleMatch] = Field(default_factory=list)
    candidate_scores: dict[str, list[RequestTypeCandidate | TeamCandidate]] = Field(
        default_factory=dict
    )
    risk_eval: RiskEval
    evaluated_decisions: list[EvaluatedDecision] = Field(default_factory=list)
    llm_assist: LlmAssistTrace = Field(default_factory=LlmAssistTrace)
    final_decision: FinalDecisionTrace


class QaAssertionResult(BaseModel):
    """Result of one log-based QA assertion."""

    assertion_id: str
    passed: bool
    request_id: str | None = None
    message: str | None = None
    severity: Literal["info", "warning", "error"] = "error"
