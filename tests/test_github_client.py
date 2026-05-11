from src.github_client import build_github_issue_payload
from src.schema import AutomationDecision, Priority, Team, TicketDraft


def test_build_github_issue_payload_is_dry_run_and_idempotent() -> None:
    draft = TicketDraft(
        request_id="REQ-GH-001",
        title="[Bug] 결제 오류 확인",
        body="결제 오류 확인 요청입니다.",
        labels=["bug", "urgent"],
        assignee_team=Team.ENGINEERING,
        priority=Priority.URGENT,
        source_decision=AutomationDecision.READY_FOR_APPROVAL,
    )

    payload = build_github_issue_payload(draft)
    payload_again = build_github_issue_payload(draft)

    assert payload is not None
    assert payload_again is not None
    assert payload.dry_run is True
    assert payload.idempotency_key == payload_again.idempotency_key
    assert payload.title == "[Bug] 결제 오류 확인"
    assert "Dry-run only" in payload.body
    assert "engineering" in payload.labels
