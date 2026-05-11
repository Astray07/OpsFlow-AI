"""Automation decision layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.rule_engine import RuleEngineEvaluation
from src.schema import AutomationDecision, EvaluatedDecision, RawRequest, RequestType, RiskLevel


DEFAULT_AUTOMATION_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "automation_policy.yml"
)
RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}
UNSAFE_OR_DISALLOWED_KEYWORDS = (
    "개인정보 원문",
    "원문을 추출",
    "보안 우회",
    "토큰 원문",
    "비밀번호 원문",
    "password",
    "credential",
    "secret",
)
POLICY_BLOCKED_KEYWORDS = (
    "자동화하지 말고",
    "자동화 금지",
    "직접 확인해야",
)


@dataclass(frozen=True)
class AutomationPolicy:
    """Automation policy loaded from config."""

    version: str
    decision_order: list[AutomationDecision]
    rules: dict[AutomationDecision, dict[str, Any]]


@dataclass(frozen=True)
class DecisionResult:
    """Final decision and trace for one request."""

    automation_decision: AutomationDecision
    needs_review: bool
    review_reason: str | None
    decision_reasons: list[str]
    evaluated_decisions: list[EvaluatedDecision]


def load_automation_policy(
    path: str | Path = DEFAULT_AUTOMATION_POLICY_PATH,
) -> AutomationPolicy:
    """Load automation decision policy from YAML."""

    policy_path = Path(path)
    with policy_path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, Mapping):
        raise ValueError(f"Automation policy must be a YAML mapping: {policy_path}")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Automation policy is missing version: {policy_path}")

    raw_order = payload.get("decision_order")
    if not isinstance(raw_order, list) or not raw_order:
        raise ValueError(f"Automation policy is missing decision_order: {policy_path}")

    decision_order = [AutomationDecision(item) for item in raw_order]
    rules = {
        decision: dict(payload.get(decision.value, {}))
        for decision in AutomationDecision
    }

    return AutomationPolicy(version=version, decision_order=decision_order, rules=rules)


def decide_automation(
    raw_request: RawRequest,
    evaluation: RuleEngineEvaluation,
    policy: AutomationPolicy | None = None,
    *,
    pii_detected: bool = False,
) -> DecisionResult:
    """Apply the configured decision cascade to a rule-engine evaluation."""

    active_policy = policy or load_automation_policy()
    evaluated_decisions: list[EvaluatedDecision] = []

    for decision in active_policy.decision_order:
        matched, triggers = _evaluate_decision_step(
            decision,
            raw_request,
            evaluation,
            active_policy,
            pii_detected=pii_detected,
        )
        trigger = ";".join(triggers) if triggers else None
        evaluated_decisions.append(
            EvaluatedDecision(step=decision, matched=matched, trigger=trigger)
        )

        if matched:
            decision_reasons = _decision_reasons(decision, triggers)
            return DecisionResult(
                automation_decision=decision,
                needs_review=decision
                in {AutomationDecision.REJECT, AutomationDecision.REVIEW_REQUIRED},
                review_reason=_review_reason(decision, triggers),
                decision_reasons=decision_reasons,
                evaluated_decisions=evaluated_decisions,
            )

    raise ValueError("Automation policy did not produce a final decision")


def _evaluate_decision_step(
    decision: AutomationDecision,
    raw_request: RawRequest,
    evaluation: RuleEngineEvaluation,
    policy: AutomationPolicy,
    *,
    pii_detected: bool,
) -> tuple[bool, list[str]]:
    if decision == AutomationDecision.REJECT:
        triggers = _reject_triggers(raw_request, evaluation)
        return bool(triggers), triggers

    if decision == AutomationDecision.REVIEW_REQUIRED:
        triggers = _review_required_triggers(evaluation, policy, pii_detected=pii_detected)
        return bool(triggers), triggers

    if decision == AutomationDecision.DRAFT_ONLY:
        draft_eligible = _is_draft_only_eligible(evaluation, policy)
        ready_eligible = _is_ready_for_approval_eligible(evaluation, policy)
        matched = draft_eligible and not ready_eligible
        return matched, ["draft_only_threshold_met"] if matched else []

    if decision == AutomationDecision.READY_FOR_APPROVAL:
        matched = _is_ready_for_approval_eligible(evaluation, policy)
        return matched, ["ready_for_approval_threshold_met"] if matched else []

    return False, []


def _reject_triggers(raw_request: RawRequest, evaluation: RuleEngineEvaluation) -> list[str]:
    text = raw_request.raw_text.casefold()
    triggers: list[str] = []

    if evaluation.request_type == RequestType.OTHER and _matches_any(
        text,
        ("지원하지 않는 요청", "처리 불가", "unsupported"),
    ):
        triggers.append("unsupported_request_type")

    if _matches_any(text, POLICY_BLOCKED_KEYWORDS):
        triggers.append("policy_blocked")

    if _matches_any(text, UNSAFE_OR_DISALLOWED_KEYWORDS):
        triggers.append("unsafe_or_disallowed_request")

    return list(dict.fromkeys(triggers))


def _review_required_triggers(
    evaluation: RuleEngineEvaluation,
    policy: AutomationPolicy,
    *,
    pii_detected: bool,
) -> list[str]:
    triggers: list[str] = []
    configured_triggers = set(policy.rules[AutomationDecision.REVIEW_REQUIRED].get("triggers", []))
    draft_rule = policy.rules[AutomationDecision.DRAFT_ONLY]
    min_request_type_confidence = float(draft_rule.get("min_request_type_confidence", 0.75))
    min_team_confidence = float(draft_rule.get("min_team_confidence", 0.75))

    if (
        evaluation.missing_fields
        and "required_missing_fields_present" in configured_triggers
    ):
        triggers.append("required_missing_fields_present")

    if _has_multiple_team_candidates(evaluation) and "multiple_team_candidates" in configured_triggers:
        triggers.append("multiple_team_candidates")

    if (
        evaluation.request_type == RequestType.OTHER
        or evaluation.request_type_confidence < min_request_type_confidence
        or evaluation.target_team_confidence < min_team_confidence
    ) and "low_confidence" in configured_triggers:
        triggers.append("low_confidence")

    if pii_detected and "pii_detected" in configured_triggers:
        triggers.append("pii_detected")

    if evaluation.risk_level == RiskLevel.HIGH and "high_risk_action" in configured_triggers:
        triggers.append("high_risk_action")

    return list(dict.fromkeys(triggers))


def _is_draft_only_eligible(
    evaluation: RuleEngineEvaluation,
    policy: AutomationPolicy,
) -> bool:
    rule = policy.rules[AutomationDecision.DRAFT_ONLY]
    return (
        evaluation.request_type != RequestType.OTHER
        and evaluation.request_type_confidence
        >= float(rule.get("min_request_type_confidence", 0.75))
        and evaluation.target_team_confidence >= float(rule.get("min_team_confidence", 0.75))
        and _missing_fields_allowed(evaluation, rule)
        and _risk_at_or_below(evaluation.risk_level, RiskLevel(rule.get("max_risk_level", "medium")))
    )


def _is_ready_for_approval_eligible(
    evaluation: RuleEngineEvaluation,
    policy: AutomationPolicy,
) -> bool:
    rule = policy.rules[AutomationDecision.READY_FOR_APPROVAL]
    return (
        evaluation.request_type != RequestType.OTHER
        and evaluation.request_type_confidence
        >= float(rule.get("min_request_type_confidence", 0.85))
        and evaluation.target_team_confidence >= float(rule.get("min_team_confidence", 0.85))
        and _missing_fields_allowed(evaluation, rule)
        and _risk_at_or_below(evaluation.risk_level, RiskLevel(rule.get("max_risk_level", "low")))
    )


def _missing_fields_allowed(
    evaluation: RuleEngineEvaluation,
    rule: Mapping[str, Any],
) -> bool:
    allow_missing_fields = rule.get("allow_missing_fields", False)
    if allow_missing_fields is True:
        return True
    if allow_missing_fields == "optional_only":
        return not evaluation.missing_fields
    return not evaluation.missing_fields


def _has_multiple_team_candidates(evaluation: RuleEngineEvaluation) -> bool:
    if len(evaluation.target_team_candidates) < 2:
        return False

    top = evaluation.target_team_candidates[0]
    second = evaluation.target_team_candidates[1]
    return top.confidence - second.confidence < 0.15


def _risk_at_or_below(actual: RiskLevel, maximum: RiskLevel) -> bool:
    return RISK_ORDER[actual] <= RISK_ORDER[maximum]


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.casefold() in text for keyword in keywords)


def _decision_reasons(decision: AutomationDecision, triggers: list[str]) -> list[str]:
    if not triggers:
        return [f"{decision.value} policy matched"]
    return [f"{decision.value}: {trigger}" for trigger in triggers]


def _review_reason(decision: AutomationDecision, triggers: list[str]) -> str | None:
    if decision == AutomationDecision.READY_FOR_APPROVAL:
        return None
    if decision == AutomationDecision.DRAFT_ONLY:
        return None
    if not triggers:
        return f"{decision.value} policy matched"
    return "; ".join(triggers)
