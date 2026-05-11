from pathlib import Path

import pytest

from src.loader import load_csv_requests, load_jsonl_requests, load_requests


DATA_DIR = Path("data")


def test_load_csv_requests_converts_sample_rows_to_raw_requests() -> None:
    requests = load_requests(DATA_DIR / "sample_requests.csv")

    assert len(requests) == 30

    first = requests[0]
    assert first.request_id == "REQ-001"
    assert first.requester == "kim"
    assert first.channel == "slack"
    assert first.raw_text.startswith("A 고객사 결제 버튼 클릭 시 500 에러")
    assert first.created_at is not None
    assert first.created_at.isoformat() == "2026-05-11T09:00:00+09:00"
    assert first.metadata == {
        "customer_tier": "enterprise",
        "source": "synthetic",
    }


def test_load_jsonl_requests_supports_slack_style_metadata(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "requests.jsonl"
    jsonl_path.write_text(
        (
            '{"request_id":"REQ-003","channel":"slack","channel_id":"C0123",'
            '"user_id":"U0456","thread_ts":"1789000000.000100",'
            '"raw_text":"A 고객사 결제 오류 또 발생했습니다. 급해요.",'
            '"created_at":"2026-05-11T09:00:00+09:00"}\n'
        ),
        encoding="utf-8",
    )

    requests = load_jsonl_requests(jsonl_path)

    assert len(requests) == 1
    request = requests[0]
    assert request.request_id == "REQ-003"
    assert request.requester == "U0456"
    assert request.channel == "slack"
    assert request.metadata["channel_id"] == "C0123"
    assert request.metadata["user_id"] == "U0456"
    assert request.metadata["thread_ts"] == "1789000000.000100"


def test_load_csv_requests_rejects_missing_required_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "requests.csv"
    csv_path.write_text("request_id,channel\nREQ-001,slack\n", encoding="utf-8")

    with pytest.raises(ValueError, match="raw_text"):
        load_csv_requests(csv_path)


def test_load_requests_rejects_unsupported_extension(tmp_path: Path) -> None:
    input_path = tmp_path / "requests.txt"
    input_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported input file extension"):
        load_requests(input_path)
