"""Ticket draft builder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.human_text import (
    clarification_question_for_request,
    format_decision_reasons,
    format_extracted_fields,
    format_missing_fields,
)
from src.privacy import mask_pii
from src.schema import AutomationDecision, NormalizedRequest, TicketDraft


DEFAULT_TICKET_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "ticket_templates.yml"
)


@dataclass(frozen=True)
class TicketTemplateConfig:
    """Ticket template config loaded from YAML."""

    version: str
    templates: dict[str, dict[str, Any]]


def load_ticket_templates(
    path: str | Path = DEFAULT_TICKET_TEMPLATE_PATH,
) -> TicketTemplateConfig:
    """Load ticket templates from YAML."""

    template_path = Path(path)
    with template_path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, Mapping):
        raise ValueError(f"Ticket templates must be a YAML mapping: {template_path}")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Ticket templates are missing version: {template_path}")

    templates = {
        key: dict(value)
        for key, value in payload.items()
        if key != "version" and isinstance(value, Mapping)
    }
    return TicketTemplateConfig(version=version, templates=templates)


def build_ticket_drafts(
    normalized_requests: list[NormalizedRequest],
    templates: TicketTemplateConfig | None = None,
) -> list[TicketDraft]:
    """Build ticket drafts for requests that are eligible for ticket output."""

    active_templates = templates or load_ticket_templates()
    drafts: list[TicketDraft] = []
    for request in normalized_requests:
        draft = build_ticket_draft(request, active_templates)
        if draft is not None:
            drafts.append(draft)
    return drafts


def build_ticket_draft(
    request: NormalizedRequest,
    templates: TicketTemplateConfig | None = None,
) -> TicketDraft | None:
    """Build one ticket draft, or ``None`` when the request is rejected."""

    if request.automation_decision not in {
        AutomationDecision.READY_FOR_APPROVAL,
        AutomationDecision.DRAFT_ONLY,
        AutomationDecision.REVIEW_REQUIRED,
    }:
        return None

    active_templates = templates or load_ticket_templates()
    template = active_templates.templates.get(request.request_type.value, {})

    title_template = template.get("title")
    title = (
        str(title_template).format(summary=request.summary, priority=request.priority.value)
        if title_template
        else request.suggested_ticket_title
    )
    if not title:
        title = f"[{request.request_type.value}] {request.summary}"

    labels = [
        str(label).format(priority=request.priority.value)
        for label in template.get("labels", [])
    ]
    if not labels:
        labels = [request.request_type.value, request.priority.value]

    body = _build_body(request, template.get("body_sections", []))

    return TicketDraft(
        request_id=request.request_id,
        title=title,
        body=body,
        labels=labels,
        assignee_team=request.target_team,
        priority=request.priority,
        source_decision=request.automation_decision,
    )


def _build_body(request: NormalizedRequest, body_sections: list[str]) -> str:
    if not body_sections:
        return request.suggested_ticket_body or _fallback_body(request)

    sections: list[str] = []
    for section in body_sections:
        rendered = _render_section(section, request)
        if rendered:
            sections.append(rendered)

    return "\n\n".join(sections) if sections else _fallback_body(request)


def _render_section(section: str, request: NormalizedRequest) -> str | None:
    extracted = request.extracted_fields
    extracted_dict = _safe_extracted_fields(request)

    section_renderers = {
        "summary": lambda: f"## 요약\n{request.summary}",
        "original_request": lambda: f"## 원문 요청\n{_safe_request_text(request)}",
        "extracted_fields": lambda: f"## 추출 필드\n{format_extracted_fields(extracted_dict)}",
        "missing_information": lambda: _missing_information(request),
        "suggested_next_question": lambda: _suggested_next_question(request),
        "trace": lambda: _trace_section(request),
        "requested_dataset": lambda: _field_section("요청 데이터/지표", extracted.dataset_or_metric),
        "purpose": lambda: _field_section("목적", extracted.purpose),
        "deadline": lambda: _field_section("마감일", extracted.deadline),
        "user_need": lambda: _field_section("사용자 니즈", extracted.user_need),
        "expected_outcome": lambda: _field_section("기대 결과", extracted.expected_outcome),
        "priority_reason": lambda: _field_section("우선순위 근거", extracted.priority_reason),
    }

    renderer = section_renderers.get(section)
    if renderer is None:
        return None
    return renderer()


def _missing_information(request: NormalizedRequest) -> str:
    return f"## 누락 정보\n{format_missing_fields(request.missing_fields)}"


def _suggested_next_question(request: NormalizedRequest) -> str | None:
    question = clarification_question_for_request(request)
    if not question:
        return None
    return f"## 확인 질문\n{question}"


def _trace_section(request: NormalizedRequest) -> str:
    return f"## 판단 근거\n{format_decision_reasons(request)}"


def _field_section(title: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"## {title}\n{value}"


def _fallback_body(request: NormalizedRequest) -> str:
    return request.suggested_ticket_body or (
        f"원문 요청:\n{_safe_request_text(request)}\n\n"
        f"요청 유형: {request.request_type.value}\n"
        f"담당 팀: {request.target_team.value}\n"
        f"우선순위: {request.priority.value}\n"
        f"위험도: {request.risk_level.value}"
    )


def _safe_request_text(request: NormalizedRequest) -> str:
    if request.pii_detected and request.masked_text:
        return request.masked_text
    return request.raw_text


def _safe_extracted_fields(request: NormalizedRequest) -> dict[str, object]:
    extracted = request.extracted_fields.model_dump(exclude_none=True)
    if not request.pii_detected:
        return extracted

    return {
        field_name: mask_pii(value).masked_text if isinstance(value, str) else value
        for field_name, value in extracted.items()
    }
