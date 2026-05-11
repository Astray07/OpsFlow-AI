from src.rule_engine import evaluate_request, load_rule_engine_config
from src.schema import RawRequest, RequestType, RiskLevel


def test_risk_rules_raise_refund_approval_request_to_high() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-008",
        channel="form",
        raw_text="C 고객사 환불 처리 승인 부탁드립니다. 금액은 120만원이고 오늘 중 처리해야 합니다.",
        metadata={"customer_tier": "enterprise"},
    )

    evaluation = evaluate_request(raw_request, config)

    assert evaluation.request_type == RequestType.APPROVAL_REQUEST
    assert evaluation.risk_level == RiskLevel.HIGH
    assert "high.request_type.approval_request" in evaluation.matched_risk_rules
    assert "high.keyword.환불 처리 승인" in evaluation.matched_risk_rules
    assert "high.side_effect.payment_or_refund" in evaluation.matched_risk_rules


def test_pii_detected_raises_otherwise_low_risk_request_to_medium() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-024",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락해서 환불 상태를 알려주세요.",
    )

    evaluation = evaluate_request(raw_request, config, pii_detected=True)

    assert evaluation.risk_level == RiskLevel.MEDIUM
    assert "medium.pii_detected" in evaluation.matched_risk_rules

    low_side_effect_request = RawRequest(
        request_id="REQ-PII-LOW",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    pii_evaluation = evaluate_request(low_side_effect_request, config, pii_detected=True)

    assert pii_evaluation.risk_level == RiskLevel.MEDIUM
    assert "medium.pii_detected" in pii_evaluation.matched_risk_rules


def test_internal_ops_side_effect_keywords_are_loaded_from_config() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-RISK-CONFIG",
        channel="form",
        raw_text="관리자 로그인 실패가 여러 번 발생했습니다. 보안팀 확인이 필요합니다.",
    )

    evaluation = evaluate_request(raw_request, config)

    assert "관리자 로그인" in config.risk_rules["high"]["internal_ops_side_effect_keywords"]
    assert config.risk_rules["matching_semantics"]["final_risk"] == "highest_matched_level_wins"
    assert evaluation.risk_level == RiskLevel.HIGH
    assert "high.internal_ops.side_effect" in evaluation.matched_risk_rules
