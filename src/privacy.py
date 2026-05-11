"""PII detection and masking utilities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PRIVACY_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "privacy_rules.yml"
)


@dataclass(frozen=True)
class PrivacyRule:
    """One regex masking rule loaded from privacy config."""

    pii_type: str
    pattern: re.Pattern[str]
    replacement: str


@dataclass(frozen=True)
class PrivacyConfig:
    """Privacy config used by the masking layer."""

    version: str
    masking_rules: tuple[PrivacyRule, ...]
    policy: dict[str, Any]


@dataclass(frozen=True)
class PrivacyMaskingResult:
    """Result of applying PII masking to text."""

    pii_detected: bool
    pii_types: list[str]
    masked_text: str


def load_privacy_config(path: str | Path = DEFAULT_PRIVACY_CONFIG_PATH) -> PrivacyConfig:
    """Load privacy masking rules from YAML."""

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, Mapping):
        raise ValueError(f"Privacy config must be a YAML mapping: {config_path}")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Privacy config is missing a non-empty version: {config_path}")

    masking = payload.get("masking")
    if not isinstance(masking, Mapping):
        raise ValueError(f"Privacy config is missing masking rules: {config_path}")

    rules = []
    for pii_type, rule_payload in masking.items():
        if isinstance(rule_payload, Mapping) and rule_payload.get("enabled") is False:
            continue
        rules.append(_parse_privacy_rule(pii_type, rule_payload, config_path))
    policy = payload.get("policy") or {}
    if not isinstance(policy, Mapping):
        raise ValueError(f"Privacy config policy must be a mapping: {config_path}")

    return PrivacyConfig(version=version, masking_rules=tuple(rules), policy=dict(policy))


def mask_pii(text: str, config: PrivacyConfig | None = None) -> PrivacyMaskingResult:
    """Detect configured PII patterns and return masked text."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    active_config = config or load_privacy_config()
    masked_text = text
    pii_types: list[str] = []

    for rule in active_config.masking_rules:
        updated_text, match_count = rule.pattern.subn(rule.replacement, masked_text)
        if match_count:
            masked_text = updated_text
            pii_types.append(rule.pii_type)

    unique_types = list(dict.fromkeys(pii_types))
    return PrivacyMaskingResult(
        pii_detected=bool(unique_types),
        pii_types=unique_types,
        masked_text=masked_text,
    )


def _parse_privacy_rule(
    pii_type: Any, rule_payload: Any, config_path: Path
) -> PrivacyRule:
    if not isinstance(pii_type, str) or not pii_type.strip():
        raise ValueError(f"Privacy rule type must be a non-empty string: {config_path}")

    if not isinstance(rule_payload, Mapping):
        raise ValueError(f"Privacy rule '{pii_type}' must be a mapping: {config_path}")

    pattern = rule_payload.get("pattern")
    replacement = rule_payload.get("replacement")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"Privacy rule '{pii_type}' is missing pattern: {config_path}")
    if not isinstance(replacement, str):
        raise ValueError(f"Privacy rule '{pii_type}' is missing replacement: {config_path}")

    try:
        compiled_pattern = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex for privacy rule '{pii_type}': {exc}") from exc

    return PrivacyRule(
        pii_type=pii_type,
        pattern=compiled_pattern,
        replacement=replacement,
    )
