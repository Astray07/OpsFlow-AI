"""Rule-first classification and scoring layer."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.schema import (
    ExtractedFields,
    Priority,
    RawRequest,
    RequestType,
    RequestTypeCandidate,
    RiskLevel,
    Team,
    TeamCandidate,
)


DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CONFIG_FILES = {
    "request_types": "request_types.yml",
    "required_fields": "required_fields.yml",
    "team_mapping": "team_mapping.yml",
    "priority_rules": "priority_rules.yml",
    "scoring_policy": "scoring_policy.yml",
    "risk_rules": "risk_rules.yml",
    "extraction_rules": "extraction_rules.yml",
}


@dataclass(frozen=True)
class RuleEngineConfig:
    """All rule-engine YAML configs loaded into memory."""

    request_types_version: str
    required_fields_version: str
    team_mapping_version: str
    priority_rules_version: str
    scoring_policy_version: str
    risk_rules_version: str
    extraction_rules_version: str
    request_types: dict[RequestType, dict[str, Any]]
    required_fields: dict[RequestType, dict[str, list[str]]]
    team_mapping: dict[Team, dict[str, Any]]
    priority_rules: dict[Priority, dict[str, Any]]
    scoring_policy: dict[str, Any]
    risk_rules: dict[str, Any]
    extraction_rules: dict[str, Any]


@dataclass(frozen=True)
class RuleEngineEvaluation:
    """Rule-engine output before the decision layer is applied."""

    request_type: RequestType
    request_type_confidence: float
    request_type_candidates: list[RequestTypeCandidate]
    keyword_scores: dict[RequestType, float]
    extracted_fields: ExtractedFields
    missing_fields: list[str]
    target_team: Team
    target_team_confidence: float
    target_team_candidates: list[TeamCandidate]
    priority: Priority
    risk_level: RiskLevel
    matched_risk_rules: list[str]


def load_rule_engine_config(config_dir: str | Path = DEFAULT_CONFIG_DIR) -> RuleEngineConfig:
    """Load all rule-engine config files from a config directory."""

    base_path = Path(config_dir)
    payloads = {
        name: _load_yaml_mapping(base_path / file_name)
        for name, file_name in CONFIG_FILES.items()
    }

    return RuleEngineConfig(
        request_types_version=_read_version(payloads["request_types"], "request_types"),
        required_fields_version=_read_version(payloads["required_fields"], "required_fields"),
        team_mapping_version=_read_version(payloads["team_mapping"], "team_mapping"),
        priority_rules_version=_read_version(payloads["priority_rules"], "priority_rules"),
        scoring_policy_version=_read_version(payloads["scoring_policy"], "scoring_policy"),
        risk_rules_version=_read_version(payloads["risk_rules"], "risk_rules"),
        extraction_rules_version=_read_version(payloads["extraction_rules"], "extraction_rules"),
        request_types=_enum_keyed_mapping(payloads["request_types"], RequestType),
        required_fields=_enum_keyed_mapping(payloads["required_fields"], RequestType),
        team_mapping=_enum_keyed_mapping(payloads["team_mapping"], Team),
        priority_rules=_enum_keyed_mapping(payloads["priority_rules"], Priority),
        scoring_policy={k: v for k, v in payloads["scoring_policy"].items() if k != "version"},
        risk_rules={k: v for k, v in payloads["risk_rules"].items() if k != "version"},
        extraction_rules={k: v for k, v in payloads["extraction_rules"].items() if k != "version"},
    )


def evaluate_request(
    raw_request: RawRequest,
    config: RuleEngineConfig | None = None,
    *,
    pii_detected: bool = False,
    pii_min_risk_level: RiskLevel | str | None = RiskLevel.MEDIUM,
) -> RuleEngineEvaluation:
    """Evaluate one raw request with config-driven rules."""

    active_config = config or load_rule_engine_config()
    extracted_fields = extract_fields(raw_request, active_config)
    request_type_candidates, keyword_scores = build_request_type_candidates(
        raw_request, extracted_fields, active_config
    )
    top_type = request_type_candidates[0]
    missing_fields = calculate_missing_fields(top_type.type, extracted_fields, active_config)
    target_team_candidates = build_target_team_candidates(
        raw_request, top_type.type, top_type.confidence, active_config
    )
    top_team = target_team_candidates[0]
    risk_level, matched_risk_rules = calculate_risk_level(
        raw_request,
        top_type.type,
        active_config,
        pii_detected=pii_detected,
        pii_min_risk_level=pii_min_risk_level,
        missing_fields=missing_fields,
    )

    return RuleEngineEvaluation(
        request_type=top_type.type,
        request_type_confidence=top_type.confidence,
        request_type_candidates=request_type_candidates,
        keyword_scores=keyword_scores,
        extracted_fields=extracted_fields,
        missing_fields=missing_fields,
        target_team=top_team.team,
        target_team_confidence=top_team.confidence,
        target_team_candidates=target_team_candidates,
        priority=calculate_priority(raw_request, active_config),
        risk_level=risk_level,
        matched_risk_rules=matched_risk_rules,
    )


def build_request_type_candidates(
    raw_request: RawRequest,
    extracted_fields: ExtractedFields,
    config: RuleEngineConfig,
) -> tuple[list[RequestTypeCandidate], dict[RequestType, float]]:
    """Create scored request type candidates."""

    scoring_config = config.scoring_policy["request_type_confidence"]
    top_n = int(scoring_config.get("candidate_preselect_top_n", 3))
    keyword_weight = float(scoring_config.get("keyword_score_weight", 0.5))
    field_weight = float(scoring_config.get("required_field_score_weight", 0.35))
    metadata_weight = float(scoring_config.get("metadata_score_weight", 0.15))
    close_gap = float(scoring_config.get("close_candidate_gap", 0.15))
    close_penalty = float(scoring_config.get("close_candidate_penalty", 0.10))
    fallback_threshold = float(scoring_config.get("fallback_to_other_below", 0.50))

    scored_candidates: list[RequestTypeCandidate] = []
    keyword_scores: dict[RequestType, float] = {}

    for request_type, rule in config.request_types.items():
        if rule.get("fallback_only"):
            continue

        keyword_score, matched_signals = calculate_keyword_score(
            raw_request.raw_text,
            rule.get("keywords", {}),
        )
        keyword_scores[request_type] = keyword_score
        field_score = calculate_required_field_score(
            request_type, extracted_fields, config
        )
        metadata_score = calculate_metadata_score(raw_request, rule.get("metadata_conditions", {}))

        confidence = _clamp(
            keyword_weight * keyword_score
            + field_weight * field_score
            + metadata_weight * metadata_score
        )

        if confidence > 0 or matched_signals:
            scored_candidates.append(
                RequestTypeCandidate(
                    type=request_type,
                    confidence=confidence,
                    matched_signals=matched_signals,
                )
            )

    scored_candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    scored_candidates = _apply_close_candidate_penalty(
        scored_candidates[:top_n],
        close_gap,
        close_penalty,
    )

    if _is_unsafe_or_disallowed_request(raw_request.raw_text):
        fallback = RequestTypeCandidate(
            type=RequestType.OTHER,
            confidence=1.0,
            reason="unsafe request fallback",
        )
        return [fallback, *scored_candidates], keyword_scores

    should_fallback = (
        not scored_candidates
        or (
            scored_candidates[0].confidence < fallback_threshold
            and not scored_candidates[0].matched_signals
        )
    )
    if should_fallback:
        best_confidence = scored_candidates[0].confidence if scored_candidates else 0.0
        fallback_confidence = _clamp(max(0.5, 1.0 - best_confidence))
        fallback = RequestTypeCandidate(
            type=RequestType.OTHER,
            confidence=fallback_confidence,
            reason="fallback below request_type confidence threshold",
        )
        return [fallback, *scored_candidates], keyword_scores

    return scored_candidates, keyword_scores


def build_target_team_candidates(
    raw_request: RawRequest,
    request_type: RequestType,
    request_type_confidence: float,
    config: RuleEngineConfig,
) -> list[TeamCandidate]:
    """Create target team candidates from request type and team keywords."""

    if request_type == RequestType.OTHER:
        return [
            TeamCandidate(
                team=Team.UNASSIGNED,
                confidence=1.0,
                reason="other request_type fallback",
            )
        ]

    scoring_config = config.scoring_policy["target_team_confidence"]
    request_type_weight = float(scoring_config.get("request_type_confidence_weight", 0.55))
    mapping_weight = float(scoring_config.get("team_mapping_score_weight", 0.30))
    keyword_weight = float(scoring_config.get("team_keyword_score_weight", 0.15))
    multi_team_gap = float(scoring_config.get("multi_team_gap", 0.15))
    multi_team_penalty = float(scoring_config.get("multi_team_penalty", 0.10))

    candidates: list[TeamCandidate] = []
    for team, rule in config.team_mapping.items():
        mapping_score = calculate_team_mapping_score(request_type, rule)
        keyword_score, matched_signals = calculate_keyword_score(
            raw_request.raw_text,
            rule.get("keywords", {}),
        )
        if mapping_score == 0 and not matched_signals:
            continue
        confidence = _clamp(
            request_type_weight * request_type_confidence
            + mapping_weight * mapping_score
            + keyword_weight * keyword_score
        )

        if confidence > 0:
            reason = _team_reason(request_type, mapping_score)
            candidates.append(
                TeamCandidate(
                    team=team,
                    confidence=confidence,
                    reason=reason,
                    matched_signals=matched_signals,
                )
            )

    candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    penalized_candidates = _apply_close_team_penalty(
        candidates,
        multi_team_gap,
        multi_team_penalty,
    )
    return penalized_candidates or [
        TeamCandidate(
            team=Team.UNASSIGNED,
            confidence=1.0,
            reason="no matching team rule",
        )
    ]


def calculate_keyword_score(
    text: str,
    keywords: Mapping[str, int | float] | None,
) -> tuple[float, list[str]]:
    """Calculate normalized keyword score and return matched signals."""

    if not keywords:
        return 0.0, []

    lowered_text = text.casefold()
    keyword_matches: list[tuple[int, int, int, str, float]] = []
    total_weight = 0.0

    for index, (keyword, weight) in enumerate(keywords.items()):
        numeric_weight = float(weight)
        total_weight += numeric_weight
        match = re.search(re.escape(keyword.casefold()), lowered_text)
        if match:
            keyword_matches.append(
                (match.start(), match.end(), index, keyword, numeric_weight)
            )

    selected_matches: list[tuple[int, int, int, str, float]] = []
    occupied_spans: list[tuple[int, int]] = []
    for match in sorted(keyword_matches, key=lambda item: (-(item[1] - item[0]), item[2])):
        start, end, *_ = match
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied_spans):
            continue
        selected_matches.append(match)
        occupied_spans.append((start, end))

    selected_matches.sort(key=lambda item: item[2])
    matched_weight = sum(match[4] for match in selected_matches)
    matched_signals = [match[3] for match in selected_matches]

    active_total_weight = min(total_weight, 1.0)
    if active_total_weight <= 0:
        return 0.0, matched_signals

    return _clamp(matched_weight / active_total_weight), matched_signals


def extract_fields(
    raw_request: RawRequest,
    config: RuleEngineConfig | None = None,
) -> ExtractedFields:
    """Extract common fields with conservative rule-based heuristics."""

    active_config = config or load_rule_engine_config()
    text = raw_request.raw_text
    rules = active_config.extraction_rules.get("fields", {})
    extracted = ExtractedFields(
        symptom=_extract_config_field(text, rules, "symptom"),
        affected_customer_or_user=_extract_config_field(text, rules, "affected_customer_or_user"),
        impact_scope=_extract_config_field(text, rules, "impact_scope"),
        reproduction_steps=_extract_config_field(text, rules, "reproduction_steps"),
        first_seen_at=_extract_config_field(text, rules, "first_seen_at"),
        environment=_extract_config_field(text, rules, "environment"),
        dataset_or_metric=_extract_config_field(text, rules, "dataset_or_metric"),
        purpose=_extract_config_field(text, rules, "purpose"),
        deadline=_extract_config_field(text, rules, "deadline"),
        format=_extract_config_field(text, rules, "format"),
        user_need=_extract_config_field(text, rules, "user_need"),
        expected_outcome=_extract_config_field(text, rules, "expected_outcome"),
        priority_reason=_extract_config_field(text, rules, "priority_reason"),
        customer=_extract_config_field(text, rules, "customer"),
        issue_detail=_extract_config_field(text, rules, "issue_detail"),
        required_action=_extract_config_field(text, rules, "required_action"),
        contact_channel=_extract_config_field(text, rules, "contact_channel"),
        approval_target=_extract_config_field(text, rules, "approval_target"),
        scope_or_amount=_extract_config_field(text, rules, "scope_or_amount"),
        approval_owner=_extract_config_field(text, rules, "approval_owner"),
        requested_action=_extract_config_field(text, rules, "requested_action"),
        target_user_or_system=_extract_config_field(text, rules, "target_user_or_system"),
    )
    return _infer_support_action(text, extracted)


def calculate_missing_fields(
    request_type: RequestType,
    extracted_fields: ExtractedFields,
    config: RuleEngineConfig,
) -> list[str]:
    """Return missing required fields for a request type."""

    rule = config.required_fields.get(request_type, {})
    required_fields = rule.get("required", [])
    return [
        field_name
        for field_name in required_fields
        if not _field_has_value(extracted_fields, field_name)
    ]


def _infer_support_action(text: str, extracted_fields: ExtractedFields) -> ExtractedFields:
    if extracted_fields.required_action:
        return extracted_fields
    if any(keyword in text for keyword in ["결제 취소", "환불 처리 승인", "승인 부탁"]):
        return extracted_fields
    if not extracted_fields.customer or not extracted_fields.issue_detail:
        return extracted_fields
    if not any(keyword in text for keyword in ["안 온다고", "문의", "오류", "상태", "로그인"]):
        return extracted_fields
    return extracted_fields.model_copy(update={"required_action": "문제 원인 확인 및 고객 응대"})


def calculate_required_field_score(
    request_type: RequestType,
    extracted_fields: ExtractedFields,
    config: RuleEngineConfig,
) -> float:
    """Calculate required field completion ratio for a candidate type."""

    rule = config.required_fields.get(request_type, {})
    required_fields = rule.get("required", [])
    if not required_fields:
        return 1.0

    present_count = sum(
        1 for field_name in required_fields if _field_has_value(extracted_fields, field_name)
    )
    return _clamp(present_count / len(required_fields))


def calculate_metadata_score(
    raw_request: RawRequest,
    metadata_conditions: Mapping[str, list[Any]] | None,
) -> float:
    """Calculate how many configured metadata conditions match."""

    if not metadata_conditions:
        return 0.0

    match_count = 0
    for key, allowed_values in metadata_conditions.items():
        actual_value = _metadata_value(raw_request, key)
        if actual_value is not None and actual_value in allowed_values:
            match_count += 1

    return _clamp(match_count / len(metadata_conditions))


def calculate_team_mapping_score(request_type: RequestType, team_rule: Mapping[str, Any]) -> float:
    """Score how strongly a request type maps to a team."""

    request_types = team_rule.get("request_types", {})
    if request_type.value in request_types.get("primary", []):
        return 1.0
    if request_type.value in request_types.get("secondary", []):
        return 0.5
    return 0.0


def calculate_priority(raw_request: RawRequest, config: RuleEngineConfig) -> Priority:
    """Calculate request priority using ordered config rules."""

    for priority in (Priority.URGENT, Priority.HIGH, Priority.LOW):
        rule = config.priority_rules.get(priority, {})
        if _matches_list_keywords(raw_request.raw_text, rule.get("keywords", [])):
            return priority
        if calculate_metadata_score(raw_request, rule.get("metadata_conditions", {})) > 0:
            return priority

    medium_rule = config.priority_rules.get(Priority.MEDIUM, {})
    if medium_rule.get("default", False):
        return Priority.MEDIUM

    return Priority.MEDIUM


def calculate_risk_level(
    raw_request: RawRequest,
    request_type: RequestType,
    config: RuleEngineConfig,
    *,
    pii_detected: bool = False,
    pii_min_risk_level: RiskLevel | str | None = RiskLevel.MEDIUM,
    missing_fields: list[str] | None = None,
) -> tuple[RiskLevel, list[str]]:
    """Calculate risk level with highest matched level winning."""

    _validate_risk_matching_semantics(config)
    matched_rules: list[str] = []
    pii_min_risk = _coerce_risk_level(pii_min_risk_level)

    high_rule = config.risk_rules.get("high", {})
    if request_type.value in high_rule.get("request_types", []):
        matched_rules.append(f"high.request_type.{request_type.value}")
    matched_high_keywords = _matched_list_keywords(
        raw_request.raw_text,
        high_rule.get("keywords", []),
    )
    matched_rules.extend(f"high.keyword.{keyword}" for keyword in matched_high_keywords)
    matched_high_side_effects = _matched_side_effects(
        raw_request.raw_text,
        high_rule.get("side_effects", {}),
    )
    matched_rules.extend(
        f"high.side_effect.{side_effect}" for side_effect in matched_high_side_effects
    )
    if request_type == RequestType.INTERNAL_OPS and _matches_list_keywords(
        raw_request.raw_text,
        high_rule.get("internal_ops_side_effect_keywords", []),
    ):
        matched_rules.append("high.internal_ops.side_effect")
    if pii_detected and pii_min_risk == RiskLevel.HIGH:
        matched_rules.append("high.pii_detected")
    if matched_rules:
        return RiskLevel.HIGH, matched_rules

    medium_rule = config.risk_rules.get("medium", {})
    medium_matches: list[str] = []
    matched_medium_keywords = _matched_list_keywords(
        raw_request.raw_text,
        medium_rule.get("keywords", []),
    )
    medium_matches.extend(f"medium.keyword.{keyword}" for keyword in matched_medium_keywords)
    if (
        raw_request.metadata.get("customer_tier") == "enterprise"
        and (
            request_type in {RequestType.CUSTOMER_SUPPORT, RequestType.INTERNAL_OPS}
            or bool(missing_fields)
        )
    ):
        medium_matches.append("medium.enterprise_context")
    if pii_detected and pii_min_risk == RiskLevel.MEDIUM:
        medium_matches.append("medium.pii_detected")
    if medium_matches:
        return RiskLevel.MEDIUM, medium_matches

    low_matches = ["low.default"]
    if pii_detected and pii_min_risk == RiskLevel.LOW:
        low_matches.append("low.pii_detected")
    return RiskLevel.LOW, low_matches


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, Mapping):
        raise ValueError(f"Config must be a YAML mapping: {path}")
    return dict(payload)


def _read_version(payload: Mapping[str, Any], config_name: str) -> str:
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{config_name} config is missing version")
    return version


def _enum_keyed_mapping(
    payload: Mapping[str, Any],
    enum_type: type[RequestType] | type[Team] | type[Priority],
) -> dict[Any, dict[str, Any]]:
    enum_mapping: dict[Any, dict[str, Any]] = {}
    for key, value in payload.items():
        if key == "version":
            continue
        enum_key = enum_type(key)
        if not isinstance(value, Mapping):
            raise ValueError(f"Config section '{key}' must be a mapping")
        enum_mapping[enum_key] = dict(value)
    return enum_mapping


def _metadata_value(raw_request: RawRequest, key: str) -> Any:
    if key == "channel":
        return raw_request.channel
    if key == "requester":
        return raw_request.requester
    return raw_request.metadata.get(key)


def _field_has_value(extracted_fields: ExtractedFields, field_name: str) -> bool:
    value = getattr(extracted_fields, field_name, None)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _apply_close_candidate_penalty(
    candidates: list[RequestTypeCandidate],
    close_gap: float,
    close_penalty: float,
) -> list[RequestTypeCandidate]:
    if len(candidates) < 2:
        return candidates

    top_confidence = candidates[0].confidence
    if top_confidence - candidates[1].confidence >= close_gap:
        return candidates

    penalized = [
        candidate.model_copy(
            update={"confidence": _clamp(candidate.confidence - close_penalty)}
        )
        if top_confidence - candidate.confidence < close_gap
        else candidate
        for candidate in candidates
    ]
    penalized.sort(key=lambda candidate: candidate.confidence, reverse=True)
    return penalized


def _apply_close_team_penalty(
    candidates: list[TeamCandidate],
    close_gap: float,
    close_penalty: float,
) -> list[TeamCandidate]:
    if len(candidates) < 2:
        return candidates

    top_confidence = candidates[0].confidence
    if top_confidence - candidates[1].confidence >= close_gap:
        return candidates

    penalized = [
        candidate.model_copy(
            update={"confidence": _clamp(candidate.confidence - close_penalty)}
        )
        if top_confidence - candidate.confidence < close_gap
        else candidate
        for candidate in candidates
    ]
    penalized.sort(key=lambda candidate: candidate.confidence, reverse=True)
    return penalized


def _team_reason(request_type: RequestType, mapping_score: float) -> str | None:
    if mapping_score == 1.0:
        return f"{request_type.value} primary team"
    if mapping_score == 0.5:
        return f"{request_type.value} secondary team"
    return None


def _matches_list_keywords(text: str, keywords: list[str]) -> bool:
    return bool(_matched_list_keywords(text, keywords))


def _matched_list_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered_text = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in lowered_text]


def _matched_side_effects(text: str, side_effects: Mapping[str, Any]) -> list[str]:
    if not isinstance(side_effects, Mapping):
        return []

    matched: list[str] = []
    for side_effect, keywords in side_effects.items():
        if isinstance(keywords, list) and _matches_list_keywords(text, keywords):
            matched.append(side_effect)
    return matched


def _validate_risk_matching_semantics(config: RuleEngineConfig) -> None:
    semantics = config.risk_rules.get("matching_semantics", {})
    if not semantics:
        return

    if semantics.get("final_risk") != "highest_matched_level_wins":
        raise ValueError("Unsupported risk final_risk matching semantics")
    if semantics.get("within_same_bucket") != "OR":
        raise ValueError("Unsupported risk within_same_bucket matching semantics")
    if semantics.get("between_buckets") != "OR":
        raise ValueError("Unsupported risk between_buckets matching semantics")


def _coerce_risk_level(value: RiskLevel | str | None) -> RiskLevel:
    if value is None:
        return RiskLevel.MEDIUM
    if isinstance(value, RiskLevel):
        return value
    return RiskLevel(str(value).strip().lower())


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return round(min(max(value, minimum), maximum), 4)


def _extract_config_field(
    text: str,
    rules: Mapping[str, Any],
    field_name: str,
) -> str | None:
    field_rule = rules.get(field_name, {})
    if not isinstance(field_rule, Mapping):
        return None

    if any(skip in text for skip in field_rule.get("skip_contains", [])):
        return None
    if text.strip() in set(field_rule.get("skip_exact", [])):
        return None

    return _first_match(text, list(field_rule.get("patterns", [])))


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _is_unsafe_or_disallowed_request(text: str) -> bool:
    lowered = text.casefold()
    return any(
        keyword in lowered
        for keyword in [
            "개인정보 원문",
            "원문을 추출",
            "보안 우회",
            "비밀번호 원문",
            "토큰 원문",
        ]
    )
