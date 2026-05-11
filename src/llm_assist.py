"""LLM-assisted summarization and ticket draft helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.privacy import PrivacyMaskingResult
from src.rule_engine import RuleEngineEvaluation
from src.schema import AutomationDecision, LlmAssistTrace, RawRequest, RequestType, RiskLevel


DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class LlmAssistResult:
    """LLM assist output with deterministic fallback fields."""

    trace: LlmAssistTrace
    input_text: str
    summary: str | None = None
    suggested_ticket_title: str | None = None
    suggested_ticket_body: str | None = None


def should_use_llm_assist(
    evaluation: RuleEngineEvaluation,
    automation_decision: AutomationDecision,
) -> bool:
    """Return whether a request is a candidate for LLM assistance."""

    return (
        automation_decision in {AutomationDecision.REVIEW_REQUIRED, AutomationDecision.DRAFT_ONLY}
        or bool(evaluation.missing_fields)
        or evaluation.request_type == RequestType.OTHER
        or evaluation.request_type_confidence < 0.75
        or evaluation.target_team_confidence < 0.75
    )


def assist_request(
    raw_request: RawRequest,
    evaluation: RuleEngineEvaluation,
    privacy_result: PrivacyMaskingResult,
    automation_decision: AutomationDecision,
    *,
    enabled: bool | None = None,
    model_name: str | None = None,
) -> LlmAssistResult:
    """Run optional LLM assist or return a deterministic skipped trace."""

    load_env_file(override_existing=True)
    input_text = privacy_result.masked_text if privacy_result.pii_detected else raw_request.raw_text
    requested = should_use_llm_assist(evaluation, automation_decision)
    use_llm = _llm_enabled(enabled) and requested
    selected_model = model_name or os.getenv("OPSFLOW_LLM_MODEL") or DEFAULT_MODEL

    fallback_summary = _fallback_summary(input_text)
    fallback_title = _fallback_ticket_title(evaluation, fallback_summary, automation_decision)
    fallback_body = _fallback_ticket_body(
        input_text,
        evaluation,
        automation_decision,
        _clarification_question(evaluation),
    )

    if not requested:
        return LlmAssistResult(
            trace=LlmAssistTrace(used=False, reason="llm_assist_not_needed"),
            input_text=input_text,
            summary=fallback_summary,
            suggested_ticket_title=fallback_title,
            suggested_ticket_body=fallback_body,
        )

    if not use_llm:
        reason = "llm_assist_disabled"
        if enabled is None and not _env_truthy("OPSFLOW_ENABLE_LLM_ASSIST"):
            reason = "llm_assist_disabled_by_default"
        elif not os.getenv("OPENAI_API_KEY"):
            reason = "llm_assist_skipped_missing_openai_api_key"
        return LlmAssistResult(
            trace=LlmAssistTrace(
                used=False,
                reason=reason,
                suggested_clarification=_clarification_question(evaluation),
            ),
            input_text=input_text,
            summary=fallback_summary,
            suggested_ticket_title=fallback_title,
            suggested_ticket_body=fallback_body,
        )

    return _assist_with_openai(
        input_text,
        evaluation,
        automation_decision,
        selected_model,
        fallback_summary,
        fallback_title,
        fallback_body,
    )


def _assist_with_openai(
    input_text: str,
    evaluation: RuleEngineEvaluation,
    automation_decision: AutomationDecision,
    model_name: str,
    fallback_summary: str,
    fallback_title: str | None,
    fallback_body: str,
) -> LlmAssistResult:
    """Use OpenAI when explicitly enabled; fall back safely on any error."""

    try:
        from openai import OpenAI

        client = OpenAI()
        prompt = _prompt(input_text, evaluation, automation_decision)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You help draft Korean operations tickets. "
                        "Return concise Korean text and do not invent missing facts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
    except Exception as exc:  # pragma: no cover - network/API fallback path
        return LlmAssistResult(
            trace=LlmAssistTrace(
                used=False,
                reason="llm_assist_error_fallback",
                model_name=model_name,
                suggested_clarification=_clarification_question(evaluation),
                error=_sanitize_error(str(exc)),
            ),
            input_text=input_text,
            summary=fallback_summary,
            suggested_ticket_title=fallback_title,
            suggested_ticket_body=fallback_body,
        )

    return LlmAssistResult(
        trace=LlmAssistTrace(
            used=True,
            reason="llm_assist_enabled",
            model_name=model_name,
            suggested_clarification=_clarification_question(evaluation),
        ),
        input_text=input_text,
        summary=fallback_summary,
        suggested_ticket_title=fallback_title,
        suggested_ticket_body=content.strip() or fallback_body,
    )


def load_env_file(
    path: str | Path = ".env",
    *,
    override_existing: bool = False,
) -> None:
    """Load simple KEY=VALUE entries from .env without exposing values."""

    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or (key in os.environ and not override_existing):
            continue
        os.environ[key] = _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _sanitize_error(message: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_*\\-]+", "[REDACTED_OPENAI_API_KEY]", message)


def _prompt(
    input_text: str,
    evaluation: RuleEngineEvaluation,
    automation_decision: AutomationDecision,
) -> str:
    missing = ", ".join(evaluation.missing_fields) if evaluation.missing_fields else "없음"
    return (
        f"원문 요청(PII가 있으면 마스킹됨): {input_text}\n"
        f"요청 유형: {evaluation.request_type.value}\n"
        f"담당 팀: {evaluation.target_team.value}\n"
        f"우선순위: {evaluation.priority.value}\n"
        f"위험도: {evaluation.risk_level.value}\n"
        f"누락 필드: {missing}\n"
        f"자동화 결정: {automation_decision.value}\n\n"
        "티켓 초안 또는 검토자가 사용할 간단한 정리문을 작성해 주세요."
    )


def _llm_enabled(enabled: bool | None) -> bool:
    if enabled is not None:
        return enabled and bool(os.getenv("OPENAI_API_KEY"))
    return _env_truthy("OPSFLOW_ENABLE_LLM_ASSIST") and bool(os.getenv("OPENAI_API_KEY"))


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _fallback_summary(text: str, max_length: int = 80) -> str:
    first_sentence = text.split(".")[0].strip()
    summary = first_sentence or text.strip()
    if len(summary) <= max_length:
        return summary
    return f"{summary[: max_length - 3].rstrip()}..."


def _fallback_ticket_title(
    evaluation: RuleEngineEvaluation,
    summary: str,
    automation_decision: AutomationDecision,
) -> str | None:
    if automation_decision == AutomationDecision.REJECT:
        return None
    prefix = evaluation.request_type.value.replace("_", " ").title()
    return f"[{prefix}] {summary[:50]}"


def _fallback_ticket_body(
    input_text: str,
    evaluation: RuleEngineEvaluation,
    automation_decision: AutomationDecision,
    clarification_question: str | None,
) -> str:
    missing = ", ".join(evaluation.missing_fields) if evaluation.missing_fields else "없음"
    question = f"\n확인 질문: {clarification_question}" if clarification_question else ""
    return (
        f"원문 요청:\n{input_text}\n\n"
        f"요청 유형: {evaluation.request_type.value}\n"
        f"담당 팀: {evaluation.target_team.value}\n"
        f"우선순위: {evaluation.priority.value}\n"
        f"위험도: {evaluation.risk_level.value}\n"
        f"자동화 결정: {automation_decision.value}\n"
        f"누락 필드: {missing}"
        f"{question}"
    )


def _clarification_question(evaluation: RuleEngineEvaluation) -> str | None:
    if evaluation.missing_fields:
        fields = ", ".join(evaluation.missing_fields)
        return f"요청 처리를 위해 다음 정보를 알려 주세요: {fields}"
    if evaluation.request_type == RequestType.OTHER:
        return "요청 대상과 필요한 조치를 구체적으로 알려 주세요."
    if evaluation.risk_level == RiskLevel.HIGH:
        return "처리 전 승인권자와 안전 검토 범위를 확인해 주세요."
    return None
