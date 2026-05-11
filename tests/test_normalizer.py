from dataclasses import replace
from pathlib import Path

import src.normalizer as normalizer_module
from src.normalizer import normalize_request, normalize_requests
from src.privacy import load_privacy_config
from src.schema import AutomationDecision, ProcessingStatus, RawRequest, RequestType, RiskLevel


def test_normalize_request_combines_privacy_rules_engine_and_decision() -> None:
    raw_request = RawRequest(
        request_id="REQ-NORMALIZE-001",
        channel="slack",
        raw_text=(
            "A 고객사 결제 버튼 클릭 시 500 에러가 발생합니다. "
            "전체 결제 시도 중 30% 정도 실패하고 있습니다."
        ),
        metadata={"customer_tier": "standard"},
    )

    normalized_request, trace = normalize_request(raw_request)

    assert normalized_request.request_id == "REQ-NORMALIZE-001"
    assert normalized_request.request_type == RequestType.BUG_REPORT
    assert normalized_request.request_type_confidence == (
        normalized_request.request_type_candidates[0].confidence
    )
    assert normalized_request.missing_fields == []
    assert normalized_request.pii_detected is False
    assert normalized_request.masked_text == raw_request.raw_text
    assert normalized_request.llm_used is False
    assert trace.request_id == raw_request.request_id
    assert trace.final_decision.automation_decision == normalized_request.automation_decision


def test_normalize_request_uses_pii_masking_and_medium_risk() -> None:
    raw_request = RawRequest(
        request_id="REQ-NORMALIZE-PII",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )

    normalized_request, trace = normalize_request(raw_request)

    assert normalized_request.pii_detected is True
    assert normalized_request.pii_types == ["phone"]
    assert normalized_request.masked_text == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요."
    assert trace.original_text == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요."
    assert normalized_request.required_action == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요"
    assert normalized_request.extracted_fields.contact_channel == "[PHONE]"
    assert "010-1234-5678" not in (normalized_request.suggested_ticket_body or "")
    assert "010-1234-5678" not in (normalized_request.suggested_ticket_title or "")
    assert normalized_request.risk_level == RiskLevel.MEDIUM
    assert "medium.pii_detected" in trace.risk_eval.matched_rules


def test_normalize_request_uses_privacy_configured_pii_min_risk() -> None:
    privacy_config = load_privacy_config()
    privacy_config = replace(
        privacy_config,
        policy={**privacy_config.policy, "pii_detected_min_risk_level": "high"},
    )
    raw_request = RawRequest(
        request_id="REQ-NORMALIZE-PII-HIGH",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )

    normalized_request, trace = normalize_request(
        raw_request,
        privacy_config=privacy_config,
    )

    assert normalized_request.risk_level == RiskLevel.HIGH
    assert "high.pii_detected" in trace.risk_eval.matched_rules


def test_normalize_requests_loads_config_once_for_batch() -> None:
    raw_requests = [
        RawRequest(
            request_id="REQ-NORMALIZE-002",
            channel="form",
            raw_text="지난 4월 신규 가입자 수와 결제 전환율을 CSV로 받을 수 있을까요? "
            "이번 주 금요일까지 필요합니다.",
        ),
        RawRequest(
            request_id="REQ-NORMALIZE-003",
            channel="form",
            raw_text="어제 말한 거 GitHub에 올려주세요.",
        ),
    ]

    result = normalize_requests(raw_requests, Path("config"))

    assert len(result.normalized_requests) == 2
    assert len(result.execution_traces) == 2
    assert result.normalized_requests[1].request_type == RequestType.OTHER
    assert result.normalized_requests[1].automation_decision in {
        AutomationDecision.REVIEW_REQUIRED,
        AutomationDecision.REJECT,
    }


def test_normalize_requests_marks_single_failed_request_without_stopping_batch(
    monkeypatch,
) -> None:
    raw_requests = [
        RawRequest(request_id="REQ-FAIL", raw_text="처리 중 예외를 강제로 발생시킵니다."),
        RawRequest(
            request_id="REQ-OK",
            raw_text="A 고객사 결제 버튼 클릭 시 500 에러가 발생합니다. 전체 요청의 30%입니다.",
        ),
    ]
    original_normalize_request = normalizer_module.normalize_request

    def flaky_normalize_request(raw_request, **kwargs):
        if raw_request.request_id == "REQ-FAIL":
            raise RuntimeError("forced failure")
        return original_normalize_request(raw_request, **kwargs)

    monkeypatch.setattr(
        normalizer_module,
        "normalize_request",
        flaky_normalize_request,
    )

    result = normalize_requests(raw_requests, Path("config"))

    assert len(result.normalized_requests) == 2
    failed = result.normalized_requests[0]
    ok = result.normalized_requests[1]
    assert failed.processing_status == ProcessingStatus.FAILED
    assert failed.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert failed.errors == ["RuntimeError: forced failure"]
    assert result.execution_traces[0].original_text == "[PROCESSING_FAILED_TEXT_REDACTED]"
    assert ok.processing_status == ProcessingStatus.SUCCEEDED
