from src.normalizer import normalize_request
from src.qa_assertions import render_qa_assertion_report, run_qa_assertions
from src.schema import RawRequest


def test_qa_assertions_pass_for_valid_normalized_request() -> None:
    raw_request = RawRequest(
        request_id="REQ-QA-001",
        channel="form",
        raw_text="A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다.",
    )
    normalized_request, _ = normalize_request(raw_request)

    results = run_qa_assertions([normalized_request])

    assert results
    assert all(result.passed for result in results)


def test_render_qa_assertion_report_summarizes_results() -> None:
    raw_request = RawRequest(
        request_id="REQ-QA-002",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    normalized_request, _ = normalize_request(raw_request)

    report = render_qa_assertion_report(run_qa_assertions([normalized_request]))

    assert "# QA Assertion Report" in report
    assert "failed: 0" in report
