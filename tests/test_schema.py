import pytest
from pydantic import ValidationError

from src.schema import (
    AutomationDecision,
    EvaluatedDecision,
    ExecutionTrace,
    FinalDecisionTrace,
    LlmAssistTrace,
    NormalizedRequest,
    Priority,
    RequestType,
    RequestTypeCandidate,
    ReviewAction,
    ReviewQueueItem,
    RiskEval,
    RiskLevel,
    Team,
    TeamCandidate,
    TicketDraft,
)


def make_normalized_request(**overrides: object) -> NormalizedRequest:
    data = {
        "rule_config_version": "2026-05-11",
        "scoring_policy_version": "scoring.2026-05-11",
        "risk_policy_version": "risk.2026-05-11",
        "privacy_policy_version": "privacy_rules.2026-05-11",
        "request_id": "REQ-001",
        "raw_text": "A 고객사 결제 오류가 발생했습니다.",
        "masked_text": "A 고객사 결제 오류가 발생했습니다.",
        "request_type": RequestType.BUG_REPORT,
        "request_type_confidence": 0.88,
        "request_type_candidates": [
            RequestTypeCandidate(
                type=RequestType.BUG_REPORT,
                confidence=0.88,
                matched_signals=["오류"],
            )
        ],
        "summary": "A 고객사 결제 오류 확인",
        "required_action": "결제 오류 원인 확인",
        "target_team": Team.ENGINEERING,
        "target_team_confidence": 0.86,
        "target_team_candidates": [
            TeamCandidate(
                team=Team.ENGINEERING,
                confidence=0.86,
                reason="bug_report default_team",
            )
        ],
        "priority": Priority.HIGH,
        "risk_level": RiskLevel.MEDIUM,
        "pii_detected": False,
        "missing_fields": ["impact_scope"],
        "needs_review": True,
        "review_reason": "영향 범위 누락",
        "decision_reasons": ["impact_scope 필드 누락"],
        "llm_used": False,
        "automation_decision": AutomationDecision.REVIEW_REQUIRED,
    }
    data.update(overrides)
    return NormalizedRequest(**data)


def test_normalized_request_accepts_valid_review_required() -> None:
    request = make_normalized_request()

    assert request.request_type == RequestType.BUG_REPORT
    assert request.target_team == Team.ENGINEERING
    assert request.automation_decision == AutomationDecision.REVIEW_REQUIRED


def test_normalized_request_requires_top_request_type_candidate_mirror() -> None:
    with pytest.raises(ValidationError, match="request_type must match"):
        make_normalized_request(
            request_type=RequestType.DATA_REQUEST,
            request_type_confidence=0.88,
        )


def test_ready_for_approval_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError, match="ready_for_approval requires no missing_fields"):
        make_normalized_request(
            risk_level=RiskLevel.LOW,
            missing_fields=["impact_scope"],
            needs_review=False,
            review_reason=None,
            automation_decision=AutomationDecision.READY_FOR_APPROVAL,
        )


def test_pii_detected_requires_masked_text() -> None:
    with pytest.raises(ValidationError, match="pii_detected requests must include masked_text"):
        make_normalized_request(
            pii_detected=True,
            pii_types=["PHONE"],
            masked_text=None,
        )


def test_ticket_draft_rejects_rejected_request_source() -> None:
    with pytest.raises(ValidationError, match="rejected requests should not produce ticket drafts"):
        TicketDraft(
            request_id="REQ-001",
            title="[Rejected] Unsupported request",
            body="No ticket should be created.",
            assignee_team=Team.UNASSIGNED,
            priority=Priority.LOW,
            source_decision=AutomationDecision.REJECT,
        )


def test_review_queue_item_accepts_candidates() -> None:
    item = ReviewQueueItem(
        request_id="REQ-001",
        raw_text="지난번 데이터 다시 주세요.",
        suggested_type=RequestType.DATA_REQUEST,
        suggested_team=Team.DATA,
        type_candidates=[RequestType.DATA_REQUEST, RequestType.OTHER],
        team_candidates=[Team.DATA],
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.LOW,
        review_reason="데이터 대상 누락",
        suggested_question="어떤 데이터 또는 리포트를 의미하시나요?",
        review_action=ReviewAction.ASK_CLARIFICATION,
    )

    assert item.review_action == ReviewAction.ASK_CLARIFICATION


def test_execution_trace_records_decision_cascade() -> None:
    trace = ExecutionTrace(
        request_id="REQ-002",
        original_text="지난번 데이터 다시 주세요.",
        rule_config_version="2026-05-11",
        scoring_policy_version="scoring.2026-05-11",
        risk_policy_version="risk.2026-05-11",
        privacy_policy_version="privacy_rules.2026-05-11",
        risk_eval=RiskEval(risk_level=RiskLevel.LOW),
        evaluated_decisions=[
            EvaluatedDecision(step=AutomationDecision.REJECT, matched=False),
            EvaluatedDecision(
                step=AutomationDecision.REVIEW_REQUIRED,
                matched=True,
                trigger="required_missing_fields_present",
            ),
        ],
        llm_assist=LlmAssistTrace(used=True, reason="요청 대상 데이터가 불명확함"),
        final_decision=FinalDecisionTrace(
            automation_decision=AutomationDecision.REVIEW_REQUIRED,
            decision_reasons=["dataset_or_metric 필드 누락"],
            review_reason="dataset_or_metric 필드 누락",
        ),
    )

    assert trace.evaluated_decisions[1].matched is True
