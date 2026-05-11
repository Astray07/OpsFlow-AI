import json
import os
from pathlib import Path

from src.main import run_pipeline


def test_run_pipeline_writes_normalized_requests_and_execution_log(tmp_path: Path) -> None:
    input_path = tmp_path / "requests.csv"
    output_dir = tmp_path / "outputs"
    input_path.write_text(
        (
            "request_id,requester,channel,raw_text,created_at,customer_tier\n"
            'REQ-CLI-001,kim,slack,"A 고객사 결제 버튼 클릭 시 500 에러가 발생합니다. '
            '전체 결제 시도 중 30% 정도 실패하고 있습니다.",2026-05-11T09:00:00+09:00,standard\n'
        ),
        encoding="utf-8",
    )

    result = run_pipeline(input_path, "config", output_dir)

    normalized_path = output_dir / "normalized_requests.json"
    masked_normalized_path = output_dir / "masked_normalized_requests.json"
    execution_log_path = output_dir / "execution_log.json"
    ticket_drafts_path = output_dir / "ticket_drafts.json"
    github_dry_run_path = output_dir / "github_dry_run.json"
    review_queue_path = output_dir / "review_queue.csv"
    masked_review_queue_path = output_dir / "masked_review_queue.csv"
    evaluation_report_path = output_dir / "evaluation_report.md"
    qa_report_path = output_dir / "qa_assertion_report.md"

    assert len(result.normalized_requests) == 1
    assert normalized_path.exists()
    assert masked_normalized_path.exists()
    assert execution_log_path.exists()
    assert ticket_drafts_path.exists()
    assert github_dry_run_path.exists()
    assert review_queue_path.exists()
    assert masked_review_queue_path.exists()
    assert evaluation_report_path.exists()
    assert qa_report_path.exists()

    normalized_payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    trace_payload = json.loads(execution_log_path.read_text(encoding="utf-8"))
    ticket_payload = json.loads(ticket_drafts_path.read_text(encoding="utf-8"))
    github_payload = json.loads(github_dry_run_path.read_text(encoding="utf-8"))
    review_queue_text = review_queue_path.read_text(encoding="utf-8")
    evaluation_report = evaluation_report_path.read_text(encoding="utf-8")
    qa_report = qa_report_path.read_text(encoding="utf-8")

    assert normalized_payload[0]["request_id"] == "REQ-CLI-001"
    assert normalized_payload[0]["request_type"] == "bug_report"
    assert trace_payload[0]["request_id"] == "REQ-CLI-001"
    assert isinstance(ticket_payload, list)
    assert isinstance(github_payload, list)
    assert "request_id,suggested_type,suggested_team" in review_queue_text
    assert "# Evaluation Report" in evaluation_report
    assert "# QA Assertion Report" in qa_report


def test_run_pipeline_writes_masked_shareable_exports(tmp_path: Path) -> None:
    input_path = tmp_path / "requests.csv"
    output_dir = tmp_path / "outputs"
    input_path.write_text(
        (
            "request_id,requester,channel,raw_text,created_at,customer_tier\n"
            'REQ-CLI-PII,kim,form,"010-1234-5678 고객에게 환불 상태를 알려주세요.",'
            "2026-05-11T09:00:00+09:00,standard\n"
        ),
        encoding="utf-8",
    )

    run_pipeline(input_path, "config", output_dir, gold_path=None)

    normalized_text = (output_dir / "normalized_requests.json").read_text(encoding="utf-8")
    masked_normalized_text = (output_dir / "masked_normalized_requests.json").read_text(
        encoding="utf-8"
    )
    review_queue_text = (output_dir / "review_queue.csv").read_text(encoding="utf-8")
    masked_review_queue_text = (output_dir / "masked_review_queue.csv").read_text(
        encoding="utf-8"
    )

    assert "010-1234-5678" in normalized_text
    assert "010-1234-5678" in review_queue_text
    assert "010-1234-5678" not in masked_normalized_text
    assert "010-1234-5678" not in masked_review_queue_text
    assert "[PHONE]" in masked_normalized_text
    assert "[PHONE]" in masked_review_queue_text


def test_run_pipeline_can_prefer_local_dotenv_for_cli(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "requests.csv"
    output_dir = tmp_path / "outputs"
    env_path = tmp_path / ".env"
    input_path.write_text(
        (
            "request_id,requester,channel,raw_text,created_at,customer_tier\n"
            'REQ-CLI-ENV,kim,slack,"결제 안 됩니다.",2026-05-11T09:00:00+09:00,standard\n'
        ),
        encoding="utf-8",
    )
    env_path.write_text("OPENAI_API_KEY=sk-from-local-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-parent")

    run_pipeline(
        input_path,
        Path(__file__).resolve().parents[1] / "config",
        output_dir,
        gold_path=None,
        dotenv_override=True,
    )

    assert os.environ["OPENAI_API_KEY"] == "sk-from-local-file"
