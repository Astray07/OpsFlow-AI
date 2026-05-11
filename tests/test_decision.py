from src.decision import AutomationPolicy, decide_automation, load_automation_policy
from src.rule_engine import RuleEngineEvaluation
from src.schema import (
    AutomationDecision,
    ExtractedFields,
    Priority,
    RawRequest,
    RequestType,
    RequestTypeCandidate,
    RiskLevel,
    Team,
    TeamCandidate,
)


def make_evaluation(**overrides: object) -> RuleEngineEvaluation:
    request_type = overrides.pop("request_type", RequestType.BUG_REPORT)
    request_type_confidence = overrides.pop("request_type_confidence", 0.9)
    target_team = overrides.pop("target_team", Team.ENGINEERING)
    target_team_confidence = overrides.pop("target_team_confidence", 0.9)

    data = {
        "request_type": request_type,
        "request_type_confidence": request_type_confidence,
        "request_type_candidates": [
            RequestTypeCandidate(
                type=request_type,
                confidence=request_type_confidence,
                matched_signals=["오류"],
            )
        ],
        "keyword_scores": {request_type: request_type_confidence},
        "extracted_fields": ExtractedFields(
            symptom="500 에러",
            affected_customer_or_user="A 고객사",
            impact_scope="전체 결제 시도 중 30%",
        ),
        "missing_fields": [],
        "target_team": target_team,
        "target_team_confidence": target_team_confidence,
        "target_team_candidates": [
            TeamCandidate(
                team=target_team,
                confidence=target_team_confidence,
                reason="primary team",
            )
        ],
        "priority": Priority.HIGH,
        "risk_level": RiskLevel.LOW,
        "matched_risk_rules": ["low.default"],
    }
    data.update(overrides)
    return RuleEngineEvaluation(**data)


def test_load_automation_policy_preserves_configured_decision_order() -> None:
    policy = load_automation_policy()

    assert policy.version == "automation_policy.2026-05-11"
    assert policy.decision_order == [
        AutomationDecision.REJECT,
        AutomationDecision.REVIEW_REQUIRED,
        AutomationDecision.DRAFT_ONLY,
        AutomationDecision.READY_FOR_APPROVAL,
    ]


def test_ready_for_approval_is_not_shadowed_by_draft_only() -> None:
    raw_request = RawRequest(
        request_id="REQ-READY",
        raw_text="A 고객사 결제 버튼 클릭 시 500 에러가 발생합니다. 전체 30% 실패합니다.",
    )
    evaluation = make_evaluation()

    result = decide_automation(raw_request, evaluation)

    assert result.automation_decision == AutomationDecision.READY_FOR_APPROVAL
    assert result.needs_review is False
    assert [step.step for step in result.evaluated_decisions] == [
        AutomationDecision.REJECT,
        AutomationDecision.REVIEW_REQUIRED,
        AutomationDecision.DRAFT_ONLY,
        AutomationDecision.READY_FOR_APPROVAL,
    ]
    assert result.evaluated_decisions[-1].matched is True


def test_draft_only_matches_when_confidence_is_below_ready_threshold() -> None:
    raw_request = RawRequest(
        request_id="REQ-DRAFT",
        raw_text="월간 리텐션 대시보드에 국가별 필터를 추가하고 싶습니다.",
    )
    evaluation = make_evaluation(
        request_type=RequestType.FEATURE_REQUEST,
        request_type_confidence=0.8,
        target_team=Team.PRODUCT,
        target_team_confidence=0.8,
    )

    result = decide_automation(raw_request, evaluation)

    assert result.automation_decision == AutomationDecision.DRAFT_ONLY
    assert result.needs_review is False
    assert result.evaluated_decisions[-1].trigger == "draft_only_threshold_met"


def test_review_required_precedes_ready_when_required_fields_are_missing() -> None:
    raw_request = RawRequest(
        request_id="REQ-REVIEW",
        raw_text="결제 안 됩니다.",
    )
    evaluation = make_evaluation(
        request_type_confidence=0.9,
        target_team_confidence=0.9,
        missing_fields=["affected_customer_or_user", "impact_scope"],
    )

    result = decide_automation(raw_request, evaluation)

    assert result.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert result.needs_review is True
    assert result.review_reason == "required_missing_fields_present"


def test_high_risk_action_requires_review_before_draft_or_ready() -> None:
    raw_request = RawRequest(
        request_id="REQ-HIGH-RISK",
        raw_text="C 고객사 환불 처리 승인 부탁드립니다. 금액은 120만원입니다.",
    )
    evaluation = make_evaluation(
        request_type=RequestType.APPROVAL_REQUEST,
        target_team=Team.OPS,
        risk_level=RiskLevel.HIGH,
        matched_risk_rules=["high.request_type.approval_request"],
    )

    result = decide_automation(raw_request, evaluation)

    assert result.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert result.review_reason == "high_risk_action"


def test_reject_precedes_review_for_policy_blocked_unsafe_request() -> None:
    raw_request = RawRequest(
        request_id="REQ-REJECT",
        raw_text="자동화하지 말고 보안팀이 직접 확인해야 합니다. 고객 개인정보 원문을 추출해 주세요.",
    )
    evaluation = make_evaluation(
        request_type=RequestType.OTHER,
        request_type_confidence=0.5,
        target_team=Team.UNASSIGNED,
        target_team_confidence=1.0,
        risk_level=RiskLevel.HIGH,
    )

    result = decide_automation(raw_request, evaluation)

    assert result.automation_decision == AutomationDecision.REJECT
    assert result.needs_review is True
    assert result.review_reason == "policy_blocked; unsafe_or_disallowed_request"
    assert len(result.evaluated_decisions) == 1


def test_reject_keywords_are_loaded_from_policy_config() -> None:
    raw_request = RawRequest(
        request_id="REQ-CONFIG-REJECT",
        raw_text="이 요청은 실험 정책상 차단 문구입니다.",
    )
    evaluation = make_evaluation(
        request_type=RequestType.OTHER,
        request_type_confidence=0.5,
        target_team=Team.UNASSIGNED,
        target_team_confidence=1.0,
        risk_level=RiskLevel.HIGH,
    )
    base_policy = load_automation_policy()
    rules = {decision: dict(rule) for decision, rule in base_policy.rules.items()}
    rules[AutomationDecision.REJECT]["trigger_keywords"] = {
        "policy_blocked": ["실험 정책상 차단"],
    }
    policy = AutomationPolicy(
        version=base_policy.version,
        decision_order=list(base_policy.decision_order),
        rules=rules,
    )

    result = decide_automation(raw_request, evaluation, policy)

    assert result.automation_decision == AutomationDecision.REJECT
    assert result.review_reason == "policy_blocked"
