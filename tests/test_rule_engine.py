from src.rule_engine import evaluate_request, load_rule_engine_config
from src.schema import Priority, RawRequest, RequestType, RiskLevel, Team


def test_rule_engine_evaluates_clear_bug_request() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-001",
        requester="kim",
        channel="slack",
        raw_text=(
            "A 고객사 결제 버튼 클릭 시 500 에러가 발생합니다. "
            "전체 결제 시도 중 30% 정도 실패하고 있습니다."
        ),
        metadata={"customer_tier": "enterprise"},
    )

    evaluation = evaluate_request(raw_request, config)

    assert evaluation.request_type == RequestType.BUG_REPORT
    assert evaluation.request_type_confidence >= 0.6
    assert evaluation.request_type_candidates[0].type == RequestType.BUG_REPORT
    assert "에러" in evaluation.request_type_candidates[0].matched_signals
    assert evaluation.target_team == Team.ENGINEERING
    assert evaluation.priority == Priority.URGENT
    assert evaluation.risk_level == RiskLevel.LOW
    assert evaluation.extracted_fields.symptom is not None
    assert evaluation.extracted_fields.affected_customer_or_user == "A 고객사"
    assert evaluation.extracted_fields.impact_scope is not None
    assert evaluation.missing_fields == []
    assert config.extraction_rules_version == "extraction_rules.2026-05-11"
    assert "symptom" in config.extraction_rules["fields"]


def test_rule_engine_falls_back_to_other_for_low_signal_request() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-012",
        channel="form",
        raw_text="어제 말한 거 GitHub에 올려주세요.",
    )

    evaluation = evaluate_request(raw_request, config)

    assert evaluation.request_type == RequestType.OTHER
    assert evaluation.target_team == Team.UNASSIGNED


def test_rule_engine_infers_clear_customer_support_action() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-017",
        channel="slack",
        raw_text=(
            "E 고객사에서 비밀번호 재설정 메일이 안 온다고 합니다. "
            "고객은 enterprise 등급입니다."
        ),
        metadata={"customer_tier": "enterprise"},
    )

    evaluation = evaluate_request(raw_request, config)

    assert evaluation.request_type == RequestType.CUSTOMER_SUPPORT
    assert evaluation.extracted_fields.required_action == "문제 원인 확인 및 고객 응대"
    assert "required_action" not in evaluation.missing_fields


def test_rule_engine_does_not_treat_order_id_as_approval_scope() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-013",
        channel="slack",
        raw_text="주문번호 ORD-12345 고객이 결제 취소를 요청했습니다. 처리 가능할까요?",
    )

    evaluation = evaluate_request(raw_request, config, pii_detected=True)

    assert evaluation.request_type == RequestType.APPROVAL_REQUEST
    assert evaluation.extracted_fields.scope_or_amount is None
    assert evaluation.missing_fields == ["scope_or_amount", "approval_owner"]
