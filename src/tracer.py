"""Execution trace helpers."""

from __future__ import annotations

from src.llm_assist import LlmAssistResult
from src.privacy import PrivacyConfig
from src.rule_engine import RuleEngineConfig, RuleEngineEvaluation
from src.schema import (
    EvaluatedDecision,
    ExecutionTrace,
    FinalDecisionTrace,
    NormalizedRequest,
    RawRequest,
    RiskEval,
    RuleMatch,
)


def build_execution_trace(
    raw_request: RawRequest,
    evaluation: RuleEngineEvaluation,
    evaluated_decisions: list[EvaluatedDecision],
    normalized_request: NormalizedRequest,
    rule_config: RuleEngineConfig,
    privacy_config: PrivacyConfig,
    llm_assist: LlmAssistResult,
) -> ExecutionTrace:
    """Build an execution trace for one normalized request."""

    trace_text = (
        normalized_request.masked_text
        if normalized_request.pii_detected and normalized_request.masked_text
        else raw_request.raw_text
    )
    return ExecutionTrace(
        request_id=raw_request.request_id,
        original_text=trace_text,
        rule_config_version=rule_config.request_types_version,
        scoring_policy_version=rule_config.scoring_policy_version,
        risk_policy_version=rule_config.risk_rules_version,
        privacy_policy_version=privacy_config.version,
        rule_matches=_rule_matches(evaluation),
        candidate_scores={
            "request_type": evaluation.request_type_candidates,
            "target_team": evaluation.target_team_candidates,
        },
        risk_eval=RiskEval(
            risk_level=evaluation.risk_level,
            matched_rules=evaluation.matched_risk_rules,
        ),
        evaluated_decisions=evaluated_decisions,
        llm_assist=llm_assist.trace,
        final_decision=FinalDecisionTrace(
            automation_decision=normalized_request.automation_decision,
            decision_reasons=normalized_request.decision_reasons,
            review_reason=normalized_request.review_reason,
        ),
    )


def _rule_matches(evaluation: RuleEngineEvaluation) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    for candidate in evaluation.request_type_candidates:
        for signal in candidate.matched_signals:
            matches.append(
                RuleMatch(
                    rule_id=f"request_type.{candidate.type.value}.keyword",
                    matched_keyword=signal,
                    suggested_type=candidate.type,
                    weight=candidate.confidence,
                )
            )
    for candidate in evaluation.target_team_candidates:
        for signal in candidate.matched_signals:
            matches.append(
                RuleMatch(
                    rule_id=f"target_team.{candidate.team.value}.keyword",
                    matched_keyword=signal,
                    suggested_team=candidate.team,
                    weight=candidate.confidence,
                )
            )
    return matches
