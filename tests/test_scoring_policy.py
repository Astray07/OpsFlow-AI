from src.rule_engine import calculate_keyword_score, load_rule_engine_config
from src.schema import RequestType


def test_keyword_score_uses_configured_weights_and_clamps_to_one() -> None:
    config = load_rule_engine_config()
    keywords = config.request_types[RequestType.BUG_REPORT]["keywords"]

    single_score, single_matches = calculate_keyword_score("결제 오류가 발생했습니다.", keywords)
    full_score, full_matches = calculate_keyword_score("오류 에러 장애가 모두 보입니다.", keywords)

    assert single_score == 0.7
    assert single_matches == ["오류", "결제"]
    assert full_score == 1.0
    assert full_matches == ["오류", "장애", "에러"]
