"""Request normalization layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from src.decision import AutomationPolicy, decide_automation, load_automation_policy
from src.human_text import (
    REQUEST_TYPE_LABELS,
    RISK_LABELS,
    format_decision_reasons,
    format_missing_fields,
)
from src.loader import load_requests
from src.llm_assist import assist_request
from src.privacy import PrivacyConfig, load_privacy_config, mask_pii
from src.rule_engine import RuleEngineConfig, RuleEngineEvaluation, evaluate_request, load_rule_engine_config
from src.schema import (
    AutomationDecision,
    EvaluatedDecision,
    ExecutionTrace,
    ExtractedFields,
    FinalDecisionTrace,
    LlmAssistTrace,
    NormalizedRequest,
    Priority,
    ProcessingStatus,
    RawRequest,
    RequestType,
    RequestTypeCandidate,
    RiskEval,
    RiskLevel,
    Team,
    TeamCandidate,
)
from src.tracer import build_execution_trace


@dataclass(frozen=True)
class NormalizationResult:
    """Normalized requests and traces generated from one batch."""

    normalized_requests: list[NormalizedRequest]
    execution_traces: list[ExecutionTrace]


def normalize_file(
    input_path: str | Path,
    config_dir: str | Path = Path("config"),
    *,
    llm_assist_enabled: bool | None = None,
) -> NormalizationResult:
    """Load raw requests from a file and normalize them."""

    raw_requests = load_requests(input_path)
    return normalize_requests(
        raw_requests,
        config_dir,
        llm_assist_enabled=llm_assist_enabled,
    )


def normalize_requests(
    raw_requests: list[RawRequest],
    config_dir: str | Path = Path("config"),
    *,
    llm_assist_enabled: bool | None = None,
) -> NormalizationResult:
    """Normalize a batch of raw requests."""

    base_config_dir = Path(config_dir)
    rule_config = load_rule_engine_config(base_config_dir)
    privacy_config = load_privacy_config(base_config_dir / "privacy_rules.yml")
    automation_policy = load_automation_policy(base_config_dir / "automation_policy.yml")

    normalized_requests: list[NormalizedRequest] = []
    execution_traces: list[ExecutionTrace] = []

    for raw_request in raw_requests:
        try:
            normalized_request, trace = normalize_request(
                raw_request,
                rule_config=rule_config,
                privacy_config=privacy_config,
                automation_policy=automation_policy,
                llm_assist_enabled=llm_assist_enabled,
            )
        except Exception as exc:  # pragma: no cover - exercised through monkeypatch
            normalized_request, trace = _failed_request_result(
                raw_request,
                rule_config,
                privacy_config,
                exc,
            )
        normalized_requests.append(normalized_request)
        execution_traces.append(trace)

    return NormalizationResult(
        normalized_requests=normalized_requests,
        execution_traces=execution_traces,
    )


def normalize_request(
    raw_request: RawRequest,
    *,
    rule_config: RuleEngineConfig | None = None,
    privacy_config: PrivacyConfig | None = None,
    automation_policy: AutomationPolicy | None = None,
    llm_assist_enabled: bool | None = None,
) -> tuple[NormalizedRequest, ExecutionTrace]:
    """Normalize one raw request and return the execution trace."""

    active_rule_config = rule_config or load_rule_engine_config()
    active_privacy_config = privacy_config or load_privacy_config()
    active_automation_policy = automation_policy or load_automation_policy()

    privacy_result = mask_pii(raw_request.raw_text, active_privacy_config)
    evaluation = evaluate_request(
        raw_request,
        active_rule_config,
        pii_detected=privacy_result.pii_detected,
        pii_min_risk_level=active_privacy_config.policy.get(
            "pii_detected_min_risk_level",
            RiskLevel.MEDIUM.value,
        ),
    )
    decision = decide_automation(
        raw_request,
        evaluation,
        active_automation_policy,
        pii_detected=privacy_result.pii_detected,
    )
    llm_assist = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=llm_assist_enabled,
        send_raw_text_to_llm=bool(
            active_privacy_config.policy.get("send_raw_text_to_llm", False)
        ),
    )
    display_text = (
        privacy_result.masked_text
        if privacy_result.pii_detected
        else raw_request.raw_text
    )
    extracted_fields = (
        _mask_extracted_fields(evaluation.extracted_fields, active_privacy_config)
        if privacy_result.pii_detected
        else evaluation.extracted_fields
    )

    normalized_request = NormalizedRequest(
        rule_config_version=active_rule_config.request_types_version,
        scoring_policy_version=active_rule_config.scoring_policy_version,
        risk_policy_version=active_rule_config.risk_rules_version,
        privacy_policy_version=active_privacy_config.version,
        request_id=raw_request.request_id,
        raw_text=raw_request.raw_text,
        masked_text=privacy_result.masked_text,
        request_type=evaluation.request_type,
        request_type_confidence=evaluation.request_type_confidence,
        request_type_candidates=evaluation.request_type_candidates,
        summary=llm_assist.summary or _summarize(display_text),
        required_action=extracted_fields.required_action,
        target_team=evaluation.target_team,
        target_team_confidence=evaluation.target_team_confidence,
        target_team_candidates=evaluation.target_team_candidates,
        priority=evaluation.priority,
        risk_level=evaluation.risk_level,
        pii_detected=privacy_result.pii_detected,
        pii_types=privacy_result.pii_types,
        extracted_fields=extracted_fields,
        missing_fields=evaluation.missing_fields,
        needs_review=decision.needs_review,
        review_reason=decision.review_reason,
        decision_reasons=decision.decision_reasons,
        llm_used=llm_assist.trace.used,
        model_name=llm_assist.trace.model_name,
        suggested_clarification=llm_assist.trace.suggested_clarification,
        suggested_ticket_title=llm_assist.suggested_ticket_title
        or _ticket_title(
            evaluation,
            display_text,
            decision.automation_decision,
        ),
        suggested_ticket_body=llm_assist.suggested_ticket_body
        or _ticket_body(display_text, evaluation, decision.decision_reasons),
        automation_decision=decision.automation_decision,
    )
    trace = build_execution_trace(
        raw_request,
        evaluation,
        decision.evaluated_decisions,
        normalized_request,
        active_rule_config,
        active_privacy_config,
        llm_assist,
    )
    return normalized_request, trace


def _failed_request_result(
    raw_request: RawRequest,
    rule_config: RuleEngineConfig,
    privacy_config: PrivacyConfig,
    exc: Exception,
) -> tuple[NormalizedRequest, ExecutionTrace]:
    error_message = f"{type(exc).__name__}: {exc}"
    type_candidate = RequestTypeCandidate(
        type=RequestType.OTHER,
        confidence=1.0,
        reason="processing failure fallback",
    )
    team_candidate = TeamCandidate(
        team=Team.UNASSIGNED,
        confidence=1.0,
        reason="processing failure fallback",
    )
    decision_reasons = ["review_required: processing_failed"]
    normalized_request = NormalizedRequest(
        rule_config_version=rule_config.request_types_version,
        scoring_policy_version=rule_config.scoring_policy_version,
        risk_policy_version=rule_config.risk_rules_version,
        privacy_policy_version=privacy_config.version,
        request_id=raw_request.request_id,
        raw_text=raw_request.raw_text,
        masked_text=None,
        request_type=RequestType.OTHER,
        request_type_confidence=1.0,
        request_type_candidates=[type_candidate],
        summary=_summarize(raw_request.raw_text),
        target_team=Team.UNASSIGNED,
        target_team_confidence=1.0,
        target_team_candidates=[team_candidate],
        priority=Priority.MEDIUM,
        risk_level=RiskLevel.HIGH,
        extracted_fields={},
        missing_fields=[],
        needs_review=True,
        review_reason="processing_failed",
        decision_reasons=decision_reasons,
        automation_decision=AutomationDecision.REVIEW_REQUIRED,
        processing_status=ProcessingStatus.FAILED,
        errors=[error_message],
    )
    trace = ExecutionTrace(
        request_id=raw_request.request_id,
        original_text="[PROCESSING_FAILED_TEXT_REDACTED]",
        rule_config_version=rule_config.request_types_version,
        scoring_policy_version=rule_config.scoring_policy_version,
        risk_policy_version=rule_config.risk_rules_version,
        privacy_policy_version=privacy_config.version,
        candidate_scores={
            "request_type": [type_candidate],
            "target_team": [team_candidate],
        },
        risk_eval=RiskEval(
            risk_level=RiskLevel.HIGH,
            matched_rules=["processing_failed"],
        ),
        evaluated_decisions=[
            EvaluatedDecision(
                step=AutomationDecision.REVIEW_REQUIRED,
                matched=True,
                trigger="processing_failed",
            )
        ],
        llm_assist=LlmAssistTrace(used=False, reason="processing_failed"),
        final_decision=FinalDecisionTrace(
            automation_decision=AutomationDecision.REVIEW_REQUIRED,
            decision_reasons=decision_reasons,
            review_reason="processing_failed",
        ),
    )
    return normalized_request, trace


def _summarize(text: str, max_length: int = 80) -> str:
    first_sentence = text.split(".")[0].strip()
    summary = first_sentence or text.strip()
    if len(summary) <= max_length:
        return summary
    return f"{summary[: max_length - 3].rstrip()}..."


def _mask_extracted_fields(
    extracted_fields: ExtractedFields,
    privacy_config: PrivacyConfig,
) -> ExtractedFields:
    masked_values = {}
    for field_name, value in extracted_fields.model_dump().items():
        if isinstance(value, str):
            masked_values[field_name] = mask_pii(value, privacy_config).masked_text
        else:
            masked_values[field_name] = value
    return ExtractedFields(**masked_values)


def _ticket_title(
    evaluation: RuleEngineEvaluation,
    request_text: str,
    automation_decision: AutomationDecision,
) -> str | None:
    if automation_decision == AutomationDecision.REJECT:
        return None
    prefix = evaluation.request_type.value.replace("_", " ").title()
    return f"[{prefix}] {_summarize(request_text, 50)}"


def _ticket_body(
    request_text: str,
    evaluation: RuleEngineEvaluation,
    decision_reasons: list[str],
) -> str:
    missing = format_missing_fields(evaluation.missing_fields)
    decision_like = SimpleNamespace(
        missing_fields=evaluation.missing_fields,
        decision_reasons=decision_reasons,
        review_reason=None,
        request_type_confidence=evaluation.request_type_confidence,
        target_team_confidence=evaluation.target_team_confidence,
        target_team_candidates=evaluation.target_team_candidates,
        pii_types=[],
    )
    return (
        f"원문 요청:\n{request_text}\n\n"
        f"요청 유형: {REQUEST_TYPE_LABELS.get(evaluation.request_type, evaluation.request_type.value)}\n"
        f"담당 팀: {evaluation.target_team.value}\n"
        f"우선순위: {evaluation.priority.value}\n"
        f"위험도: {RISK_LABELS.get(evaluation.risk_level, evaluation.risk_level.value)}\n"
        f"누락 정보:\n{missing}\n\n"
        f"판단 근거:\n{format_decision_reasons(decision_like)}"
    )
