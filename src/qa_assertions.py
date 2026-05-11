"""Log-based QA assertions."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.schema import AutomationDecision, NormalizedRequest, QaAssertionResult, RequestType, RiskLevel


def load_normalized_requests(path: str | Path) -> list[NormalizedRequest]:
    """Load normalized requests from JSON output."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("normalized request output must be a JSON array")
    return [NormalizedRequest(**item) for item in payload]


def run_qa_assertions(
    normalized_requests: list[NormalizedRequest],
) -> list[QaAssertionResult]:
    """Run log/schema QA assertions against normalized requests."""

    results: list[QaAssertionResult] = []
    for request in normalized_requests:
        results.extend(
            [
                _assert_ready_has_no_missing_fields(request),
                _assert_high_risk_is_not_ready(request),
                _assert_pii_masked_before_llm(request),
                _assert_pii_not_repeated_in_generated_text(request),
                _assert_request_type_mirror(request),
                _assert_target_team_mirror(request),
                _assert_other_is_not_ready(request),
                _assert_policy_versions_present(request),
            ]
        )
    return results


def render_qa_assertion_report(results: list[QaAssertionResult]) -> str:
    """Render QA assertion results as Markdown."""

    total = len(results)
    failures = [result for result in results if not result.passed]
    lines = [
        "# QA Assertion Report",
        "",
        f"- total_assertions: {total}",
        f"- passed: {total - len(failures)}",
        f"- failed: {len(failures)}",
        "",
        "## Failed Assertions",
        "",
    ]

    if not failures:
        lines.append("No assertion failures.")
    else:
        lines.append("| assertion_id | request_id | severity | message |")
        lines.append("| --- | --- | --- | --- |")
        for failure in failures:
            lines.append(
                "| "
                f"{failure.assertion_id} | "
                f"{failure.request_id or ''} | "
                f"{failure.severity} | "
                f"{failure.message or ''} |"
            )

    return "\n".join(lines) + "\n"


def write_qa_assertion_report(
    normalized_requests: list[NormalizedRequest],
    output_path: str | Path,
) -> list[QaAssertionResult]:
    """Run assertions and write a Markdown report."""

    results = run_qa_assertions(normalized_requests)
    Path(output_path).write_text(render_qa_assertion_report(results), encoding="utf-8")
    return results


def _pass(assertion_id: str, request: NormalizedRequest) -> QaAssertionResult:
    return QaAssertionResult(
        assertion_id=assertion_id,
        passed=True,
        request_id=request.request_id,
    )


def _fail(assertion_id: str, request: NormalizedRequest, message: str) -> QaAssertionResult:
    return QaAssertionResult(
        assertion_id=assertion_id,
        passed=False,
        request_id=request.request_id,
        message=message,
    )


def _assert_ready_has_no_missing_fields(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-001-ready-has-no-missing-fields"
    if (
        request.automation_decision == AutomationDecision.READY_FOR_APPROVAL
        and request.missing_fields
    ):
        return _fail(assertion_id, request, "ready_for_approval has missing_fields")
    return _pass(assertion_id, request)


def _assert_high_risk_is_not_ready(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-002-high-risk-is-not-ready"
    if (
        request.risk_level == RiskLevel.HIGH
        and request.automation_decision == AutomationDecision.READY_FOR_APPROVAL
    ):
        return _fail(assertion_id, request, "high risk request was marked ready_for_approval")
    return _pass(assertion_id, request)


def _assert_pii_masked_before_llm(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-003-pii-masked-before-llm"
    if request.pii_detected and not request.masked_text:
        return _fail(assertion_id, request, "PII request is missing masked_text")
    if request.pii_detected and request.llm_used and request.masked_text == request.raw_text:
        return _fail(assertion_id, request, "PII request used LLM without effective masking")
    return _pass(assertion_id, request)


def _assert_pii_not_repeated_in_generated_text(
    request: NormalizedRequest,
) -> QaAssertionResult:
    assertion_id = "QA-004-pii-not-repeated-in-generated-text"
    if not request.pii_detected or not request.masked_text:
        return _pass(assertion_id, request)

    generated_text = "\n".join(
        value
        for value in [
            request.summary,
            request.required_action,
            request.suggested_ticket_title,
            request.suggested_ticket_body,
            request.extracted_fields.model_dump_json(),
        ]
        if value
    )
    if request.raw_text != request.masked_text and request.raw_text in generated_text:
        return _fail(assertion_id, request, "generated text repeats raw PII text")
    return _pass(assertion_id, request)


def _assert_request_type_mirror(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-005-request-type-top-candidate-mirror"
    if not request.request_type_candidates:
        return _fail(assertion_id, request, "missing request_type_candidates")
    top = request.request_type_candidates[0]
    if request.request_type != top.type or request.request_type_confidence != top.confidence:
        return _fail(assertion_id, request, "top request_type candidate does not mirror fields")
    return _pass(assertion_id, request)


def _assert_target_team_mirror(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-006-target-team-top-candidate-mirror"
    if not request.target_team_candidates:
        return _fail(assertion_id, request, "missing target_team_candidates")
    top = request.target_team_candidates[0]
    if request.target_team != top.team or request.target_team_confidence != top.confidence:
        return _fail(assertion_id, request, "top target_team candidate does not mirror fields")
    return _pass(assertion_id, request)


def _assert_other_is_not_ready(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-007-other-is-not-ready"
    if (
        request.request_type == RequestType.OTHER
        and request.automation_decision == AutomationDecision.READY_FOR_APPROVAL
    ):
        return _fail(assertion_id, request, "other request_type was marked ready_for_approval")
    return _pass(assertion_id, request)


def _assert_policy_versions_present(request: NormalizedRequest) -> QaAssertionResult:
    assertion_id = "QA-008-policy-versions-present"
    version_fields = [
        request.rule_config_version,
        request.scoring_policy_version,
        request.risk_policy_version,
        request.privacy_policy_version,
    ]
    if not all(version_fields):
        return _fail(assertion_id, request, "one or more policy versions are missing")
    return _pass(assertion_id, request)


def validate_normalized_payload(payload: object) -> list[QaAssertionResult]:
    """Validate JSON-like payload shape when schema construction itself may fail."""

    if not isinstance(payload, list):
        return [
            QaAssertionResult(
                assertion_id="QA-000-schema-load",
                passed=False,
                message="payload must be a JSON array",
            )
        ]

    results: list[QaAssertionResult] = []
    for item in payload:
        request_id = item.get("request_id") if isinstance(item, dict) else None
        try:
            NormalizedRequest(**item)
        except (TypeError, ValidationError) as exc:
            results.append(
                QaAssertionResult(
                    assertion_id="QA-000-schema-load",
                    passed=False,
                    request_id=request_id,
                    message=str(exc),
                )
            )
        else:
            results.append(
                QaAssertionResult(
                    assertion_id="QA-000-schema-load",
                    passed=True,
                    request_id=request_id,
                )
            )
    return results
