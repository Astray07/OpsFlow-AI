"""GitHub issue client for approved requests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.schema import AutomationDecision, TicketDraft


@dataclass(frozen=True)
class GitHubIssuePayload:
    """Dry-run GitHub issue payload."""

    request_id: str
    idempotency_key: str
    title: str
    body: str
    labels: list[str]
    assignee_team: str
    dry_run: bool = True


def build_github_issue_payload(draft: TicketDraft) -> GitHubIssuePayload | None:
    """Build a GitHub issue payload for an approval-safe ticket draft."""

    if draft.source_decision not in {
        AutomationDecision.READY_FOR_APPROVAL,
        AutomationDecision.DRAFT_ONLY,
    }:
        return None

    body = (
        f"{draft.body}\n\n"
        "---\n"
        f"OpsFlow request_id: `{draft.request_id}`\n"
        f"Source decision: `{draft.source_decision.value}`\n"
        "Dry-run only: no external issue was created."
    )
    labels = list(dict.fromkeys([*draft.labels, draft.priority.value, draft.assignee_team.value]))

    return GitHubIssuePayload(
        request_id=draft.request_id,
        idempotency_key=_idempotency_key(draft.request_id, draft.title),
        title=draft.title,
        body=body,
        labels=labels,
        assignee_team=draft.assignee_team.value,
    )


def build_github_dry_run_payloads(drafts: list[TicketDraft]) -> list[dict[str, Any]]:
    """Build JSON-serializable dry-run issue payloads."""

    payloads: list[dict[str, Any]] = []
    for draft in drafts:
        payload = build_github_issue_payload(draft)
        if payload is not None:
            payloads.append(payload.__dict__)
    return payloads


def write_github_dry_run(
    drafts: list[TicketDraft],
    output_path: str | Path,
) -> list[dict[str, Any]]:
    """Write GitHub dry-run payloads to JSON."""

    payloads = build_github_dry_run_payloads(drafts)
    Path(output_path).write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payloads


def _idempotency_key(request_id: str, title: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{title}".encode("utf-8")).hexdigest()[:16]
    return f"opsflow-{request_id}-{digest}"
