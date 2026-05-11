"""Review queue output builder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.schema import AutomationDecision, NormalizedRequest, ReviewAction, ReviewQueueItem


DEFAULT_REVIEW_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "review_policy.yml"
)


@dataclass(frozen=True)
class ReviewPolicy:
    """Review queue routing policy loaded from YAML."""

    version: str
    action_priority: list[ReviewAction]
    actions: dict[ReviewAction, dict[str, Any]]


def load_review_policy(path: str | Path = DEFAULT_REVIEW_POLICY_PATH) -> ReviewPolicy:
    """Load review queue action policy from YAML."""

    policy_path = Path(path)
    with policy_path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, Mapping):
        raise ValueError(f"Review policy must be a YAML mapping: {policy_path}")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Review policy is missing version: {policy_path}")

    raw_actions = payload.get("actions")
    if not isinstance(raw_actions, Mapping):
        raise ValueError(f"Review policy is missing actions: {policy_path}")

    actions = {
        ReviewAction(action): dict(rule)
        for action, rule in raw_actions.items()
        if isinstance(rule, Mapping)
    }
    raw_action_priority = payload.get("action_priority", [])
    action_priority = [ReviewAction(action) for action in raw_action_priority]
    return ReviewPolicy(
        version=version,
        action_priority=action_priority,
        actions=actions,
    )


def build_review_queue(
    normalized_requests: list[NormalizedRequest],
    policy: ReviewPolicy | None = None,
) -> list[ReviewQueueItem]:
    """Build review queue items for requests that need human attention."""

    active_policy = policy or load_review_policy()
    items: list[ReviewQueueItem] = []
    for request in normalized_requests:
        item = build_review_queue_item(request, active_policy)
        if item is not None:
            items.append(item)
    return items


def build_review_queue_item(
    request: NormalizedRequest,
    policy: ReviewPolicy | None = None,
) -> ReviewQueueItem | None:
    """Build one review queue item, or ``None`` when no review is needed."""

    if not request.needs_review:
        return None

    active_policy = policy or load_review_policy()
    triggers = _decision_triggers(request)
    review_action = _review_action(request, triggers, active_policy)

    return ReviewQueueItem(
        request_id=request.request_id,
        raw_text=request.raw_text,
        masked_text=request.masked_text,
        suggested_type=request.request_type,
        suggested_team=request.target_team,
        type_candidates=[candidate.type for candidate in request.request_type_candidates],
        team_candidates=[candidate.team for candidate in request.target_team_candidates],
        priority=request.priority,
        risk_level=request.risk_level,
        review_reason=request.review_reason or "; ".join(triggers),
        suggested_question=_suggested_question(request),
        decision_reasons=request.decision_reasons,
        review_action=review_action,
        pii_detected=request.pii_detected,
    )


def review_queue_rows(items: list[ReviewQueueItem]) -> list[dict[str, str | bool]]:
    """Serialize review queue items into CSV-friendly rows."""

    rows: list[dict[str, str | bool]] = []
    for item in items:
        rows.append(
            {
                "request_id": item.request_id,
                "suggested_type": item.suggested_type.value,
                "suggested_team": item.suggested_team.value,
                "type_candidates": ";".join(candidate.value for candidate in item.type_candidates),
                "team_candidates": ";".join(candidate.value for candidate in item.team_candidates),
                "priority": item.priority.value,
                "risk_level": item.risk_level.value,
                "review_reason": item.review_reason,
                "suggested_question": item.suggested_question or "",
                "review_action": item.review_action.value,
                "pii_detected": item.pii_detected,
                "masked_text": item.masked_text or "",
                "raw_text": item.raw_text,
            }
        )
    return rows


def _review_action(
    request: NormalizedRequest,
    triggers: set[str],
    policy: ReviewPolicy,
) -> ReviewAction:
    if request.automation_decision == AutomationDecision.REJECT:
        return ReviewAction.REJECT

    if request.pii_detected:
        triggers.add("pii_detected")

    for action in policy.action_priority:
        rule = policy.actions.get(action)
        if not rule:
            continue
        configured_triggers = set(rule.get("when", []))
        if configured_triggers & triggers:
            return action

    return ReviewAction.HOLD


def _decision_triggers(request: NormalizedRequest) -> set[str]:
    triggers: set[str] = set()
    if request.review_reason:
        triggers.update(part.strip() for part in request.review_reason.split(";") if part.strip())

    for reason in request.decision_reasons:
        if ":" in reason:
            triggers.add(reason.split(":", 1)[1].strip())
        else:
            triggers.add(reason.strip())

    return triggers


def _suggested_question(request: NormalizedRequest) -> str | None:
    if not request.missing_fields:
        return None
    fields = ", ".join(request.missing_fields)
    return f"누락된 필드를 보완해 주세요: {fields}"
