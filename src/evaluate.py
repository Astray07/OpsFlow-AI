"""Evaluation report generator."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from src.decision import AutomationPolicy, decide_automation, load_automation_policy
from src.rule_engine import RuleEngineEvaluation
from src.schema import AutomationDecision, NormalizedRequest, RawRequest


AUTOMATED_DECISIONS = {
    AutomationDecision.READY_FOR_APPROVAL.value,
    AutomationDecision.DRAFT_ONLY.value,
}
REVIEW_DECISIONS = {
    AutomationDecision.REVIEW_REQUIRED.value,
    AutomationDecision.REJECT.value,
}
THRESHOLDS = (0.65, 0.75, 0.85)


@dataclass(frozen=True)
class EvaluationReport:
    """Evaluation metrics for normalized request predictions."""

    total_predictions: int
    total_gold: int
    compared: int
    request_type_accuracy: float
    target_team_accuracy: float
    priority_accuracy: float
    risk_level_accuracy: float
    decision_accuracy: float
    missing_fields_exact_match: float
    automation_coverage: float
    false_automation_rate: float
    over_automation_rate: float
    review_recall: float
    review_precision: float
    threshold_rows: list[dict[str, float]]
    mismatches: list[dict[str, str]]


def load_predictions(path: str | Path) -> list[NormalizedRequest]:
    """Load normalized request predictions from JSON output."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("prediction output must be a JSON array")
    return [NormalizedRequest(**item) for item in payload]


def load_gold_labels(path: str | Path) -> dict[str, dict[str, str]]:
    """Load labeled request gold data."""

    with Path(path).open(encoding="utf-8", newline="") as file:
        return {row["request_id"]: row for row in csv.DictReader(file)}


def evaluate_predictions(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> EvaluationReport:
    """Compare predictions with gold labels."""

    prediction_by_id = {prediction.request_id: prediction for prediction in predictions}
    compared_ids = sorted(set(prediction_by_id) & set(gold_labels))
    compared_predictions = [prediction_by_id[request_id] for request_id in compared_ids]

    request_type_accuracy = _accuracy(
        compared_predictions,
        gold_labels,
        lambda item: item.request_type.value,
        "expected_request_type",
    )
    target_team_accuracy = _accuracy(
        compared_predictions,
        gold_labels,
        lambda item: item.target_team.value,
        "expected_target_team",
    )
    priority_accuracy = _accuracy(
        compared_predictions,
        gold_labels,
        lambda item: item.priority.value,
        "expected_priority",
    )
    risk_level_accuracy = _accuracy(
        compared_predictions,
        gold_labels,
        lambda item: item.risk_level.value,
        "expected_risk_level",
    )
    decision_accuracy = _accuracy(
        compared_predictions,
        gold_labels,
        lambda item: item.automation_decision.value,
        "expected_automation_decision",
    )
    missing_fields_exact_match = _missing_fields_exact_match(
        compared_predictions,
        gold_labels,
    )

    automation_coverage = _ratio(
        sum(
            1
            for prediction in compared_predictions
            if prediction.automation_decision.value in AUTOMATED_DECISIONS
        ),
        len(compared_predictions),
    )
    false_automation_rate = _false_automation_rate(compared_predictions, gold_labels)
    over_automation_rate = _over_automation_rate(compared_predictions, gold_labels)
    review_recall = _review_recall(compared_predictions, gold_labels)
    review_precision = _review_precision(compared_predictions, gold_labels)
    threshold_rows = _threshold_sweep(compared_predictions, gold_labels)
    mismatches = _mismatches(compared_predictions, gold_labels)

    return EvaluationReport(
        total_predictions=len(predictions),
        total_gold=len(gold_labels),
        compared=len(compared_predictions),
        request_type_accuracy=request_type_accuracy,
        target_team_accuracy=target_team_accuracy,
        priority_accuracy=priority_accuracy,
        risk_level_accuracy=risk_level_accuracy,
        decision_accuracy=decision_accuracy,
        missing_fields_exact_match=missing_fields_exact_match,
        automation_coverage=automation_coverage,
        false_automation_rate=false_automation_rate,
        over_automation_rate=over_automation_rate,
        review_recall=review_recall,
        review_precision=review_precision,
        threshold_rows=threshold_rows,
        mismatches=mismatches,
    )


def render_evaluation_report(report: EvaluationReport) -> str:
    """Render evaluation metrics as Markdown."""

    lines = [
        "# Evaluation Report",
        "",
        "## Scope",
        "",
        f"- total_predictions: {report.total_predictions}",
        f"- total_gold: {report.total_gold}",
        f"- compared: {report.compared}",
        "",
        "## Core Metrics",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| request_type_accuracy | {_pct(report.request_type_accuracy)} |",
        f"| target_team_accuracy | {_pct(report.target_team_accuracy)} |",
        f"| priority_accuracy | {_pct(report.priority_accuracy)} |",
        f"| risk_level_accuracy | {_pct(report.risk_level_accuracy)} |",
        f"| decision_accuracy | {_pct(report.decision_accuracy)} |",
        f"| missing_fields_exact_match | {_pct(report.missing_fields_exact_match)} |",
        f"| automation_coverage | {_pct(report.automation_coverage)} |",
        f"| false_automation_rate | {_pct(report.false_automation_rate)} |",
        f"| over_automation_rate | {_pct(report.over_automation_rate)} |",
        f"| review_recall | {_pct(report.review_recall)} |",
        f"| review_precision | {_pct(report.review_precision)} |",
        "",
        "## Threshold Sweep",
        "",
        "| threshold | automation_coverage | false_automation_rate | review_recall |",
        "| ---: | ---: | ---: | ---: |",
    ]

    for row in report.threshold_rows:
        lines.append(
            f"| {row['threshold']:.2f} | "
            f"{_pct(row['automation_coverage'])} | "
            f"{_pct(row['false_automation_rate'])} | "
            f"{_pct(row['review_recall'])} |"
        )

    lines.extend(["", "## Mismatches", ""])
    if not report.mismatches:
        lines.append("No mismatches on compared labels.")
    else:
        lines.append("| request_id | field | predicted | expected |")
        lines.append("| --- | --- | --- | --- |")
        for mismatch in report.mismatches[:50]:
            lines.append(
                "| "
                f"{mismatch['request_id']} | "
                f"{mismatch['field']} | "
                f"{mismatch['predicted']} | "
                f"{mismatch['expected']} |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- 이 리포트는 현재 rule-only baseline 기준입니다.",
            "- 초기 데이터는 synthetic 중심이므로 실제 운영 분포와 다를 수 있습니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_evaluation_report(
    prediction_path: str | Path,
    gold_path: str | Path,
    output_path: str | Path,
) -> EvaluationReport:
    """Load predictions and gold labels, then write a Markdown report."""

    predictions = load_predictions(prediction_path)
    gold_labels = load_gold_labels(gold_path)
    report = evaluate_predictions(predictions, gold_labels)
    Path(output_path).write_text(render_evaluation_report(report), encoding="utf-8")
    return report


def _accuracy(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
    predicted_value: object,
    gold_key: str,
) -> float:
    if not predictions:
        return 0.0

    correct = 0
    for prediction in predictions:
        if predicted_value(prediction) == gold_labels[prediction.request_id].get(gold_key):
            correct += 1
    return _ratio(correct, len(predictions))


def _missing_fields_exact_match(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> float:
    if not predictions:
        return 0.0

    correct = 0
    for prediction in predictions:
        predicted = set(prediction.missing_fields)
        expected = _split_missing_fields(
            gold_labels[prediction.request_id].get("expected_missing_fields", "")
        )
        if predicted == expected:
            correct += 1
    return _ratio(correct, len(predictions))


def _false_automation_rate(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> float:
    automated = [
        prediction
        for prediction in predictions
        if prediction.automation_decision.value in AUTOMATED_DECISIONS
    ]
    false_automated = [
        prediction
        for prediction in automated
        if gold_labels[prediction.request_id]["expected_automation_decision"] in REVIEW_DECISIONS
    ]
    return _ratio(len(false_automated), len(automated))


def _over_automation_rate(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> float:
    ready_predictions = [
        prediction
        for prediction in predictions
        if prediction.automation_decision == AutomationDecision.READY_FOR_APPROVAL
    ]
    over_automated = [
        prediction
        for prediction in ready_predictions
        if gold_labels[prediction.request_id]["expected_automation_decision"]
        != AutomationDecision.READY_FOR_APPROVAL.value
    ]
    return _ratio(len(over_automated), len(ready_predictions))


def _review_recall(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> float:
    gold_review = [
        prediction
        for prediction in predictions
        if gold_labels[prediction.request_id]["expected_automation_decision"] in REVIEW_DECISIONS
    ]
    caught = [
        prediction
        for prediction in gold_review
        if prediction.automation_decision.value in REVIEW_DECISIONS
    ]
    return _ratio(len(caught), len(gold_review))


def _review_precision(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> float:
    predicted_review = [
        prediction
        for prediction in predictions
        if prediction.automation_decision.value in REVIEW_DECISIONS
    ]
    correct_review = [
        prediction
        for prediction in predicted_review
        if gold_labels[prediction.request_id]["expected_automation_decision"] in REVIEW_DECISIONS
    ]
    return _ratio(len(correct_review), len(predicted_review))


def _threshold_sweep(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    base_policy = load_automation_policy()
    for threshold in THRESHOLDS:
        policy = _policy_with_threshold(base_policy, threshold)
        automated_ids = {
            prediction.request_id
            for prediction in predictions
            if _swept_decision(prediction, policy).value in AUTOMATED_DECISIONS
        }
        predicted_review_ids = {
            prediction.request_id
            for prediction in predictions
            if prediction.request_id not in automated_ids
        }
        false_automated = {
            request_id
            for request_id in automated_ids
            if gold_labels[request_id]["expected_automation_decision"] in REVIEW_DECISIONS
        }
        gold_review_ids = {
            prediction.request_id
            for prediction in predictions
            if gold_labels[prediction.request_id]["expected_automation_decision"] in REVIEW_DECISIONS
        }
        caught_review = predicted_review_ids & gold_review_ids
        rows.append(
            {
                "threshold": threshold,
                "automation_coverage": _ratio(len(automated_ids), len(predictions)),
                "false_automation_rate": _ratio(len(false_automated), len(automated_ids)),
                "review_recall": _ratio(len(caught_review), len(gold_review_ids)),
            }
        )
    return rows


def _policy_with_threshold(
    base_policy: AutomationPolicy,
    threshold: float,
) -> AutomationPolicy:
    rules = {decision: dict(rule) for decision, rule in base_policy.rules.items()}
    for decision in (
        AutomationDecision.READY_FOR_APPROVAL,
        AutomationDecision.DRAFT_ONLY,
    ):
        rules[decision]["min_request_type_confidence"] = threshold
        rules[decision]["min_team_confidence"] = threshold

    return AutomationPolicy(
        version=base_policy.version,
        decision_order=list(base_policy.decision_order),
        rules=rules,
    )


def _swept_decision(
    prediction: NormalizedRequest,
    policy: AutomationPolicy,
) -> AutomationDecision:
    raw_request = RawRequest(
        request_id=prediction.request_id,
        raw_text=prediction.raw_text,
    )
    evaluation = RuleEngineEvaluation(
        request_type=prediction.request_type,
        request_type_confidence=prediction.request_type_confidence,
        request_type_candidates=prediction.request_type_candidates,
        keyword_scores={},
        extracted_fields=prediction.extracted_fields,
        missing_fields=prediction.missing_fields,
        target_team=prediction.target_team,
        target_team_confidence=prediction.target_team_confidence,
        target_team_candidates=prediction.target_team_candidates,
        priority=prediction.priority,
        risk_level=prediction.risk_level,
        matched_risk_rules=[],
    )
    result = decide_automation(
        raw_request,
        evaluation,
        policy,
        pii_detected=prediction.pii_detected,
    )
    return result.automation_decision


def _mismatches(
    predictions: list[NormalizedRequest],
    gold_labels: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    fields = [
        ("request_type", "expected_request_type", lambda item: item.request_type.value),
        ("target_team", "expected_target_team", lambda item: item.target_team.value),
        ("priority", "expected_priority", lambda item: item.priority.value),
        ("risk_level", "expected_risk_level", lambda item: item.risk_level.value),
        (
            "automation_decision",
            "expected_automation_decision",
            lambda item: item.automation_decision.value,
        ),
    ]
    mismatches: list[dict[str, str]] = []
    for prediction in predictions:
        gold = gold_labels[prediction.request_id]
        for field_name, gold_key, getter in fields:
            predicted = getter(prediction)
            expected = gold.get(gold_key, "")
            if predicted != expected:
                mismatches.append(
                    {
                        "request_id": prediction.request_id,
                        "field": field_name,
                        "predicted": predicted,
                        "expected": expected,
                    }
                )
    return mismatches


def _split_missing_fields(value: str) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(";") if item.strip()}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"
