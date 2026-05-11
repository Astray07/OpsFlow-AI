import os

from src.decision import decide_automation
from src.llm_assist import assist_request, load_env_file, should_use_llm_assist
from src.privacy import mask_pii
from src.rule_engine import evaluate_request
from src.schema import AutomationDecision, RawRequest


def test_should_use_llm_assist_for_missing_fields_review_request() -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-001",
        channel="form",
        raw_text="A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )

    assert decision.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert should_use_llm_assist(evaluation, decision.automation_decision) is True


def test_assist_request_uses_masked_text_for_pii_when_llm_is_skipped() -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-PII",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )

    result = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=False,
    )

    assert result.trace.used is False
    assert result.input_text == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요."
    assert "010-1234-5678" not in result.suggested_ticket_body
    assert result.trace.suggested_clarification is not None


def test_env_example_uses_supported_llm_variable_names(monkeypatch) -> None:
    monkeypatch.delenv("OPSFLOW_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPS_FLOW_MODEL", raising=False)

    load_env_file(".env.example")

    assert "OPSFLOW_LLM_MODEL" in os.environ
    assert "OPS_FLOW_MODEL" not in os.environ
