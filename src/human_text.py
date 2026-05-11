"""Human-facing labels and explanations for generated review artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from src.schema import RequestType, RiskLevel


REVIEW_CONFIDENCE_THRESHOLD = 0.75

FIELD_LABELS = {
    "symptom": "증상",
    "affected_customer_or_user": "영향받는 고객/사용자",
    "impact_scope": "영향 범위",
    "reproduction_steps": "재현 조건",
    "first_seen_at": "최초 발생 시점",
    "environment": "환경",
    "dataset_or_metric": "데이터/지표",
    "purpose": "사용 목적",
    "deadline": "마감일/처리 희망 시점",
    "format": "형식",
    "delivery_channel": "전달 채널",
    "refresh_frequency": "갱신 주기",
    "user_need": "사용자 니즈",
    "expected_outcome": "기대 결과",
    "priority_reason": "우선순위 근거",
    "target_release": "대상 릴리스",
    "customer": "고객",
    "issue_detail": "문의/문제 내용",
    "required_action": "필요한 조치",
    "contact_channel": "연락 채널",
    "approval_target": "승인 대상",
    "scope_or_amount": "처리 범위/금액",
    "approval_owner": "승인권자",
    "policy_reference": "적용 정책/근거",
    "requested_action": "요청 조치",
    "target_user_or_system": "대상 사용자/시스템",
}

FIELD_DESCRIPTIONS = {
    "symptom": "어떤 오류나 문제가 발생했는지",
    "affected_customer_or_user": "어느 고객사, 사용자, 요청이 영향을 받는지",
    "impact_scope": "일부 사용자 문제인지, 전체 요청/고객에 영향을 주는지",
    "reproduction_steps": "문제를 다시 확인할 수 있는 조건이나 단계",
    "first_seen_at": "문제가 처음 확인된 시점",
    "environment": "브라우저, 리전, API 등 문제가 발생한 환경",
    "dataset_or_metric": "추출해야 하는 데이터셋, 리포트, 지표 이름",
    "purpose": "데이터나 작업 결과를 어디에 쓰려는지",
    "deadline": "언제까지 처리해야 하는지",
    "format": "CSV, PDF 같은 결과물 형식",
    "delivery_channel": "결과를 전달할 채널",
    "refresh_frequency": "반복 생성 또는 갱신 주기",
    "user_need": "사용자가 겪는 문제나 원하는 개선점",
    "expected_outcome": "요청이 완료되면 기대하는 상태",
    "priority_reason": "긴급하거나 중요한 이유",
    "target_release": "반영을 원하는 릴리스나 일정",
    "customer": "요청과 관련된 고객",
    "issue_detail": "고객 문의나 문제의 구체적인 내용",
    "required_action": "담당자가 해야 할 확인, 답변, 처리 조치",
    "contact_channel": "전화번호, 이메일, Slack 등 연락 수단",
    "approval_target": "승인해야 하는 작업 또는 대상",
    "scope_or_amount": "승인 범위, 금액, 수량, 처리 대상",
    "approval_owner": "처리를 승인할 책임자나 팀",
    "policy_reference": "처리 가능 여부를 판단할 정책이나 기준",
    "requested_action": "내부 운영 요청에서 수행해야 할 조치",
    "target_user_or_system": "조치가 적용될 계정, 사람, 시스템",
}

REQUEST_TYPE_LABELS = {
    RequestType.BUG_REPORT: "버그/장애",
    RequestType.DATA_REQUEST: "데이터 요청",
    RequestType.CUSTOMER_SUPPORT: "고객지원",
    RequestType.FEATURE_REQUEST: "기능 요청",
    RequestType.APPROVAL_REQUEST: "승인 요청",
    RequestType.INTERNAL_OPS: "내부 운영",
    RequestType.OTHER: "기타/분류 필요",
}

RISK_LABELS = {
    RiskLevel.LOW: "낮음",
    RiskLevel.MEDIUM: "중간",
    RiskLevel.HIGH: "높음",
}


def field_label(field_name: str) -> str:
    """Return a Korean display label for an internal field name."""

    return FIELD_LABELS.get(field_name, field_name.replace("_", " "))


def format_missing_fields(fields: Iterable[str]) -> str:
    """Render missing fields as reviewer-friendly bullets."""

    field_list = list(fields)
    if not field_list:
        return "없음"

    return "\n".join(
        f"- {field_label(field_name)}: {FIELD_DESCRIPTIONS.get(field_name, '추가 확인이 필요한 정보')}"
        for field_name in field_list
    )


def format_missing_fields_inline(fields: Iterable[str]) -> str:
    """Render missing fields as a compact Korean label list."""

    field_list = list(fields)
    if not field_list:
        return "없음"
    return ", ".join(field_label(field_name) for field_name in field_list)


def format_extracted_fields(fields: Mapping[str, Any]) -> str:
    """Render extracted fields as reviewer-friendly bullets."""

    if not fields:
        return "없음"

    lines = []
    for field_name, value in fields.items():
        if value in (None, "", []):
            continue
        lines.append(f"- {field_label(field_name)}: {value}")
    return "\n".join(lines) if lines else "없음"


def format_decision_reasons(request: Any) -> str:
    """Render machine decision reasons as human-facing bullets."""

    triggers = [_reason_trigger(reason) for reason in getattr(request, "decision_reasons", [])]
    if not triggers and getattr(request, "review_reason", None):
        triggers = [
            item.strip()
            for item in str(request.review_reason).split(";")
            if item.strip()
        ]
    triggers = list(dict.fromkeys(triggers))
    if not triggers:
        return "- 별도 판단 근거 없음"

    return "\n".join(f"- {_trigger_message(trigger, request)}" for trigger in triggers)


def format_review_reason(request: Any) -> str:
    """Render review reasons as a compact CSV-friendly sentence."""

    lines = format_decision_reasons(request).splitlines()
    messages = [line.removeprefix("- ").strip() for line in lines if line.strip()]
    return " / ".join(messages)


def clarification_question_for_request(request: Any) -> str | None:
    """Return a concrete clarification question for a normalized request."""

    suggested = getattr(request, "suggested_clarification", None)
    if suggested:
        return suggested

    return clarification_question(
        request_type=getattr(request, "request_type", None),
        risk_level=getattr(request, "risk_level", None),
        missing_fields=getattr(request, "missing_fields", []),
        extracted_fields=getattr(request, "extracted_fields", None),
        text=getattr(request, "raw_text", ""),
    )


def clarification_question(
    *,
    request_type: RequestType | None,
    risk_level: RiskLevel | None,
    missing_fields: Iterable[str],
    extracted_fields: Any = None,
    text: str = "",
) -> str | None:
    """Build a specific follow-up question from request context."""

    fields = list(missing_fields)
    if fields and _is_financial_approval_context(request_type, extracted_fields, text):
        return (
            "결제 취소/환불 처리 가능 여부를 판단할 수 있도록 승인권자, "
            "적용 정책 또는 처리 범위/금액을 알려 주세요."
        )

    if set(fields) >= {"dataset_or_metric", "purpose", "deadline"}:
        return "필요한 데이터/지표, 사용 목적, 마감일을 알려 주세요."

    if fields == ["impact_scope"] or set(fields) == {"impact_scope"}:
        return "영향 범위가 특정 고객/사용자에 한정되는지, 전체에 영향을 주는지 알려 주세요."

    if fields:
        return f"요청 처리를 위해 다음 정보를 알려 주세요: {format_missing_fields_inline(fields)}"

    if request_type == RequestType.OTHER:
        return "요청 대상과 필요한 조치를 구체적으로 알려 주세요."

    if risk_level == RiskLevel.HIGH:
        return "처리 전 승인권자와 안전 검토 범위를 확인해 주세요."

    return None


def _reason_trigger(reason: str) -> str:
    if ":" not in reason:
        return reason.strip()
    return reason.split(":", 1)[1].strip()


def _trigger_message(trigger: str, request: Any) -> str:
    if trigger == "required_missing_fields_present":
        missing = format_missing_fields_inline(getattr(request, "missing_fields", []))
        return f"필수 정보가 부족합니다: {missing}"
    if trigger == "multiple_team_candidates":
        teams = _candidate_summary(getattr(request, "target_team_candidates", []), "team")
        return f"담당 팀 후보가 비슷합니다{teams}."
    if trigger == "low_confidence":
        request_type_score = getattr(request, "request_type_confidence", None)
        team_score = getattr(request, "target_team_confidence", None)
        return (
            "분류 신뢰도가 기준보다 낮습니다"
            f" (요청 유형 {_format_score(request_type_score)}, "
            f"담당 팀 {_format_score(team_score)}, 기준 {REVIEW_CONFIDENCE_THRESHOLD:.2f})."
        )
    if trigger == "pii_detected":
        pii_types = ", ".join(getattr(request, "pii_types", [])) or "감지됨"
        return f"개인정보 또는 식별자가 포함되어 마스킹 후 검토가 필요합니다: {pii_types}"
    if trigger == "high_risk_action":
        return "권한, 결제, 환불, 삭제처럼 되돌리기 어려운 고위험 조치입니다."
    if trigger == "processing_failed":
        return "처리 중 오류가 발생해 사람 검토가 필요합니다."
    if trigger == "ready_for_approval_threshold_met":
        return "필수 정보와 신뢰도 기준을 충족해 승인 후보로 분류되었습니다."
    if trigger == "draft_only_threshold_met":
        return "초안 생성 기준은 충족했지만 외부 등록 전 사람 확인이 필요합니다."
    if trigger == "policy_blocked":
        return "정책상 자동 처리하면 안 되는 요청입니다."
    if trigger == "unsafe_or_disallowed_request":
        return "민감정보 원문 추출 등 허용되지 않는 요청입니다."
    if trigger == "unsupported_request_type":
        return "현재 자동화 범위에서 지원하지 않는 요청입니다."
    return trigger.replace("_", " ")


def _candidate_summary(candidates: Iterable[Any], attr_name: str) -> str:
    values = []
    for candidate in list(candidates)[:2]:
        value = getattr(candidate, attr_name, None)
        confidence = getattr(candidate, "confidence", None)
        if value is None:
            continue
        label = getattr(value, "value", str(value))
        values.append(f"{label} {_format_score(confidence)}")
    if not values:
        return ""
    return f" ({', '.join(values)})"


def _format_score(score: Any) -> str:
    if isinstance(score, int | float):
        return f"{score:.2f}"
    return "알 수 없음"


def _is_financial_approval_context(
    request_type: RequestType | None,
    extracted_fields: Any,
    text: str,
) -> bool:
    if request_type != RequestType.APPROVAL_REQUEST:
        return False

    approval_target = getattr(extracted_fields, "approval_target", "") or ""
    scope_or_amount = getattr(extracted_fields, "scope_or_amount", "") or ""
    haystack = f"{approval_target} {scope_or_amount} {text}"
    return any(keyword in haystack for keyword in ["환불", "결제 취소", "취소"])
