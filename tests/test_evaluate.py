import json
from pathlib import Path

from src.evaluate import (
    evaluate_predictions,
    load_gold_labels,
    load_predictions,
    render_evaluation_report,
    write_evaluation_report,
)
from src.main import run_pipeline


def test_evaluate_predictions_compares_pipeline_output_to_gold(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    run_pipeline("data/sample_requests.csv", "config", output_dir)

    predictions = load_predictions(output_dir / "normalized_requests.json")
    gold = load_gold_labels("data/labeled_requests.csv")
    report = evaluate_predictions(predictions, gold)

    assert report.total_predictions == 30
    assert report.total_gold == 30
    assert report.compared == 30
    assert report.request_type_accuracy >= 0.95
    assert report.target_team_accuracy >= 0.95
    assert report.false_automation_rate == 0.0
    assert report.review_recall >= 0.95
    assert 0.0 <= report.over_automation_rate <= 1.0
    assert len(report.threshold_rows) == 3


def test_external_seed_eval_matches_gold_labels(tmp_path: Path) -> None:
    output_dir = tmp_path / "external_seed_outputs"
    run_pipeline(
        "data/external_seed_samples.csv",
        "config",
        output_dir,
        "data/external_seed_labeled_requests.csv",
    )

    predictions = load_predictions(output_dir / "normalized_requests.json")
    gold = load_gold_labels("data/external_seed_labeled_requests.csv")
    report = evaluate_predictions(predictions, gold)

    assert report.total_predictions == 8
    assert report.compared == 8
    assert report.request_type_accuracy == 1.0
    assert report.target_team_accuracy == 1.0
    assert report.decision_accuracy == 1.0
    assert report.false_automation_rate == 0.0
    assert report.review_recall == 1.0


def test_render_evaluation_report_contains_core_sections(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    run_pipeline("data/sample_requests.csv", "config", output_dir)

    report = write_evaluation_report(
        output_dir / "normalized_requests.json",
        "data/labeled_requests.csv",
        output_dir / "evaluation_report.md",
    )
    report_text = render_evaluation_report(report)
    persisted_text = (output_dir / "evaluation_report.md").read_text(encoding="utf-8")

    assert "# Evaluation Report" in report_text
    assert "## Threshold Sweep" in report_text
    assert "over_automation_rate" in report_text
    assert persisted_text.startswith("# Evaluation Report")


def test_load_predictions_rejects_non_array_payload(tmp_path: Path) -> None:
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps({"request_id": "REQ-001"}), encoding="utf-8")

    try:
        load_predictions(path)
    except ValueError as exc:
        assert "JSON array" in str(exc)
    else:
        raise AssertionError("load_predictions should reject non-array payload")
