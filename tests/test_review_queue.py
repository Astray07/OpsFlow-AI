from src.normalizer import normalize_request
from src.review_queue import build_review_queue, load_review_policy, review_queue_rows
from src.schema import AutomationDecision, RawRequest, ReviewAction


def test_review_queue_routes_missing_fields_to_clarification() -> None:
    raw_request = RawRequest(
        request_id="REQ-REVIEW-001",
        channel="form",
        raw_text="A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다.",
    )
    normalized_request, _ = normalize_request(raw_request)

    policy = load_review_policy()
    items = build_review_queue([normalized_request], policy)

    assert policy.action_priority[0] == ReviewAction.REJECT
    assert normalized_request.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert len(items) == 1
    assert items[0].review_action == ReviewAction.ASK_CLARIFICATION
    assert "영향 범위" in (items[0].suggested_question or "")
    assert "impact_scope" not in (items[0].suggested_question or "")


def test_review_queue_routes_pii_to_security_review() -> None:
    raw_request = RawRequest(
        request_id="REQ-REVIEW-PII",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    normalized_request, _ = normalize_request(raw_request)

    items = build_review_queue([normalized_request])

    assert normalized_request.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert len(items) == 1
    assert items[0].review_action == ReviewAction.SECURITY_REVIEW
    assert items[0].pii_detected is True


def test_review_queue_routes_high_risk_action_to_security_review() -> None:
    raw_request = RawRequest(
        request_id="REQ-REVIEW-HIGH",
        channel="form",
        raw_text="권한 좀 열어주세요.",
    )
    normalized_request, _ = normalize_request(raw_request)

    items = build_review_queue([normalized_request])

    assert len(items) == 1
    assert items[0].review_action == ReviewAction.SECURITY_REVIEW


def test_review_queue_rows_are_csv_friendly() -> None:
    raw_request = RawRequest(
        request_id="REQ-REVIEW-ROWS",
        channel="form",
        raw_text="A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다.",
    )
    normalized_request, _ = normalize_request(raw_request)
    items = build_review_queue([normalized_request])

    rows = review_queue_rows(items)

    assert rows[0]["request_id"] == "REQ-REVIEW-ROWS"
    assert rows[0]["suggested_type"] == "bug_report"
    assert rows[0]["review_action"] == "ask_clarification"
