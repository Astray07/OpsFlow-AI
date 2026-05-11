"""LLM-assisted summarization and ticket draft helpers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.human_text import (
    REQUEST_TYPE_LABELS,
    RISK_LABELS,
    clarification_question,
    format_missing_fields_inline,
)
from src.privacy import PrivacyMaskingResult
from src.rule_engine import RuleEngineEvaluation
from src.schema import AutomationDecision, LlmAssistTrace, RawRequest, RequestType


DEFAULT_MODEL = "gpt-4.1-mini"


class LlmAssistStructuredResponse(BaseModel):
    """Structured LLM response accepted by the assist layer."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    suggested_ticket_title: str | None = None
    suggested_ticket_body: str = Field(min_length=1)
    suggested_clarification: str | None = None


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
    send_raw_text_to_llm: bool = False,
) -> LlmAssistResult:
    """Run optional LLM assist or return a deterministic skipped trace."""

    if privacy_result.pii_detected and not send_raw_text_to_llm:
        input_text = privacy_result.masked_text
    else:
        input_text = raw_request.raw_text
    requested = should_use_llm_assist(evaluation, automation_decision)
    use_llm = _llm_enabled(enabled) and requested
    selected_model = model_name or os.getenv("OPSFLOW_LLM_MODEL") or DEFAULT_MODEL

    fallback_summary = _fallback_summary(input_text, evaluation)
    fallback_title = _fallback_ticket_title(evaluation, fallback_summary, automation_decision)
    fallback_body = _fallback_ticket_body(
        input_text,
        evaluation,
        automation_decision,
        _clarification_question(evaluation, input_text),
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
                suggested_clarification=_clarification_question(evaluation, input_text),
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
            response_format=_structured_response_format(),
            temperature=0,
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise ValueError(f"OpenAI structured response refusal: {refusal}")
        parsed_response = _parse_structured_response(message.content or "")
    except Exception as exc:  # pragma: no cover - network/API fallback path
        return LlmAssistResult(
            trace=LlmAssistTrace(
                used=False,
                reason="llm_assist_error_fallback",
                model_name=model_name,
                suggested_clarification=_clarification_question(evaluation, input_text),
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
            suggested_clarification=(
                parsed_response.suggested_clarification
                or _clarification_question(evaluation, input_text)
            ),
        ),
        input_text=input_text,
        summary=parsed_response.summary or fallback_summary,
        suggested_ticket_title=_clean_optional(parsed_response.suggested_ticket_title)
        or fallback_title,
        suggested_ticket_body=parsed_response.suggested_ticket_body or fallback_body,
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


def should_override_env_file() -> bool:
    """Return whether local dotenv should override inherited environment values."""

    return (
        os.getenv("OPSFLOW_ENV", "").strip().lower() == "local"
        or _env_truthy("OPSFLOW_DOTENV_OVERRIDE")
    )


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
    missing = format_missing_fields_inline(evaluation.missing_fields)
    return (
        f"원문 요청(PII가 있으면 마스킹됨): {input_text}\n"
        f"요청 유형: {REQUEST_TYPE_LABELS.get(evaluation.request_type, evaluation.request_type.value)}\n"
        f"담당 팀: {evaluation.target_team.value}\n"
        f"우선순위: {evaluation.priority.value}\n"
        f"위험도: {RISK_LABELS.get(evaluation.risk_level, evaluation.risk_level.value)}\n"
        f"누락 필드: {missing}\n"
        f"자동화 결정: {automation_decision.value}\n\n"
        "원문에 없는 사실은 만들지 말고, 검토자가 바로 사용할 수 있는 "
        "요약, 티켓 제목, 티켓 본문, 확인 질문을 작성해 주세요. "
        "확인 질문이 필요 없으면 null로 둡니다."
    )


def _structured_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "opsflow_llm_assist",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "원문 근거만 사용한 한 문장 요약",
                    },
                    "suggested_ticket_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "티켓 제목. reject면 null 가능",
                    },
                    "suggested_ticket_body": {
                        "type": "string",
                        "description": "담당자가 검토할 한국어 티켓 초안",
                    },
                    "suggested_clarification": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "누락 정보가 있을 때 요청자에게 물을 질문",
                    },
                },
                "required": [
                    "summary",
                    "suggested_ticket_title",
                    "suggested_ticket_body",
                    "suggested_clarification",
                ],
            },
        },
    }


def _parse_structured_response(content: str) -> LlmAssistStructuredResponse:
    return LlmAssistStructuredResponse.model_validate(json.loads(content))


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _llm_enabled(enabled: bool | None) -> bool:
    if enabled is not None:
        return enabled and bool(os.getenv("OPENAI_API_KEY"))
    return _env_truthy("OPSFLOW_ENABLE_LLM_ASSIST") and bool(os.getenv("OPENAI_API_KEY"))


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _fallback_summary(
    text: str,
    evaluation: RuleEngineEvaluation | None = None,
    max_length: int = 80,
) -> str:
    if evaluation is not None:
        if evaluation.request_type == RequestType.DATA_REQUEST and evaluation.missing_fields:
            if "지난번" in text or "다시" in text:
                return "이전 데이터 재요청으로, 데이터 대상과 목적 확인 필요"
            return "데이터 추출 요청으로, 데이터 대상과 목적 확인 필요"
        if evaluation.request_type == RequestType.BUG_REPORT and evaluation.missing_fields:
            if "결제" in text:
                return "결제 문제 확인 요청"
            return "장애/버그 확인 요청"
        if evaluation.request_type == RequestType.CUSTOMER_SUPPORT and evaluation.missing_fields:
            return "고객 문의 처리 요청으로, 문제 내용과 조치 확인 필요"
        if evaluation.request_type == RequestType.APPROVAL_REQUEST and evaluation.missing_fields:
            return "승인 요청으로, 처리 범위와 승인권자 확인 필요"

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
    missing = format_missing_fields_inline(evaluation.missing_fields)
    question = f"\n확인 질문: {clarification_question}" if clarification_question else ""
    return (
        f"원문 요청:\n{input_text}\n\n"
        f"요청 유형: {REQUEST_TYPE_LABELS.get(evaluation.request_type, evaluation.request_type.value)}\n"
        f"담당 팀: {evaluation.target_team.value}\n"
        f"우선순위: {evaluation.priority.value}\n"
        f"위험도: {RISK_LABELS.get(evaluation.risk_level, evaluation.risk_level.value)}\n"
        f"자동화 결정: {automation_decision.value}\n"
        f"누락 필드: {missing}"
        f"{question}"
    )


def _clarification_question(
    evaluation: RuleEngineEvaluation,
    input_text: str = "",
) -> str | None:
    return clarification_question(
        request_type=evaluation.request_type,
        risk_level=evaluation.risk_level,
        missing_fields=evaluation.missing_fields,
        extracted_fields=evaluation.extracted_fields,
        text=input_text,
    )
