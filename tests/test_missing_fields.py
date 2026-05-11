from src.rule_engine import evaluate_request, load_rule_engine_config
from src.schema import RawRequest, RequestType


def test_missing_fields_are_calculated_from_selected_request_type() -> None:
    config = load_rule_engine_config()
    raw_request = RawRequest(
        request_id="REQ-DATA-001",
        channel="form",
        raw_text="이번 달 고객사별 사용량 데이터를 리포트 쿼리로 주세요.",
    )

    evaluation = evaluate_request(raw_request, config)

    assert evaluation.request_type == RequestType.DATA_REQUEST
    assert evaluation.missing_fields == ["purpose"]
