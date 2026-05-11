from src.normalizer import normalize_request
from src.schema import AutomationDecision, Priority, RawRequest, Team, TicketDraft
from src.ticket_builder import build_ticket_drafts, build_ticket_draft, load_ticket_templates


def test_build_ticket_drafts_uses_configured_template_for_draftable_request() -> None:
    raw_request = RawRequest(
        request_id="REQ-TICKET-001",
        channel="slack",
        raw_text=(
            "A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다. "
            "전체 결제 시도 중 30% 정도 실패하고 있습니다."
        ),
        metadata={"customer_tier": "standard"},
    )
    normalized_request, _ = normalize_request(raw_request)

    drafts = build_ticket_drafts([normalized_request], load_ticket_templates())

    assert normalized_request.automation_decision == AutomationDecision.READY_FOR_APPROVAL
    assert len(drafts) == 1
    assert drafts[0].request_id == "REQ-TICKET-001"
    assert drafts[0].title.startswith("[Bug]")
    assert "bug" in drafts[0].labels
    assert "## 원문 요청" in drafts[0].body


def test_build_ticket_drafts_includes_review_required_requests() -> None:
    raw_request = RawRequest(
        request_id="REQ-TICKET-REVIEW",
        channel="form",
        raw_text="결제 안 됩니다.",
    )
    normalized_request, _ = normalize_request(raw_request)

    drafts = build_ticket_drafts([normalized_request])

    assert normalized_request.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert len(drafts) == 1
    assert drafts[0].request_id == "REQ-TICKET-REVIEW"
    assert drafts[0].source_decision == AutomationDecision.REVIEW_REQUIRED
    assert "## 누락 정보" in drafts[0].body
    assert "영향받는 고객/사용자" in drafts[0].body
    assert "impact_scope" not in drafts[0].body
    assert "## 확인 질문" in drafts[0].body


def test_ticket_body_renders_human_friendly_trace_reasons() -> None:
    raw_request = RawRequest(
        request_id="REQ-TICKET-TRACE",
        channel="form",
        raw_text="결제 안 됩니다.",
    )
    normalized_request, _ = normalize_request(raw_request)

    draft = build_ticket_draft(normalized_request)

    assert isinstance(draft, TicketDraft)
    assert "분류 신뢰도가 기준보다 낮습니다" in draft.body
    assert "review_required:" not in draft.body
    assert "low_confidence" not in draft.body


def test_ticket_body_uses_masked_text_for_pii_request_even_if_drafted() -> None:
    raw_request = RawRequest(
        request_id="REQ-TICKET-PII",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    normalized_request, _ = normalize_request(raw_request)
    draftable_request = normalized_request.model_copy(
        update={
            "automation_decision": AutomationDecision.DRAFT_ONLY,
            "needs_review": False,
            "review_reason": None,
            "missing_fields": [],
            "priority": Priority.MEDIUM,
            "target_team": Team.CS,
        }
    )

    draft = build_ticket_draft(draftable_request)

    assert isinstance(draft, TicketDraft)
    assert "[PHONE]" in draft.body
    assert "010-1234-5678" not in draft.body


def test_ticket_body_uses_llm_clarification_when_available() -> None:
    raw_request = RawRequest(
        request_id="REQ-TICKET-QUESTION",
        channel="form",
        raw_text="데이터 추출 부탁드립니다.",
    )
    normalized_request, _ = normalize_request(raw_request)
    request_with_clarification = normalized_request.model_copy(
        update={
            "suggested_clarification": (
                "어떤 데이터셋, 사용 목적, 필요한 마감일을 확인해 주세요."
            )
        }
    )

    draft = build_ticket_draft(request_with_clarification)

    assert isinstance(draft, TicketDraft)
    assert "## 확인 질문" in draft.body
    assert "어떤 데이터셋, 사용 목적, 필요한 마감일을 확인해 주세요." in draft.body
