"""CLI entrypoint for OpsFlow AI."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.evaluate import write_evaluation_report
from src.github_client import write_github_dry_run
from src.llm_assist import load_env_file, should_override_env_file
from src.normalizer import NormalizationResult, normalize_file
from src.qa_assertions import write_qa_assertion_report
from src.review_queue import build_review_queue, review_queue_rows
from src.ticket_builder import build_ticket_drafts


REVIEW_QUEUE_COLUMNS = [
    "request_id",
    "suggested_type",
    "suggested_team",
    "type_candidates",
    "team_candidates",
    "priority",
    "risk_level",
    "review_reason",
    "suggested_question",
    "review_action",
    "pii_detected",
    "masked_text",
    "raw_text",
]


def run_pipeline(
    input_path: str | Path,
    config_dir: str | Path,
    output_dir: str | Path,
    gold_path: str | Path | None = Path("data/labeled_requests.csv"),
    *,
    enable_llm_assist: bool | None = None,
    dotenv_override: bool | None = None,
) -> NormalizationResult:
    """Run the rule-only normalization pipeline and write JSON outputs."""

    load_env_file(
        override_existing=(
            should_override_env_file()
            if dotenv_override is None
            else dotenv_override
        )
    )
    result = normalize_file(
        input_path,
        config_dir,
        llm_assist_enabled=enable_llm_assist,
    )
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    _write_json(
        output_path / "normalized_requests.json",
        [request.model_dump(mode="json") for request in result.normalized_requests],
    )
    _write_json(
        output_path / "execution_log.json",
        [trace.model_dump(mode="json") for trace in result.execution_traces],
    )

    ticket_drafts = build_ticket_drafts(result.normalized_requests)
    review_queue = build_review_queue(result.normalized_requests)

    _write_json(
        output_path / "ticket_drafts.json",
        [draft.model_dump(mode="json") for draft in ticket_drafts],
    )
    write_github_dry_run(ticket_drafts, output_path / "github_dry_run.json")
    _write_csv(
        output_path / "review_queue.csv",
        review_queue_rows(review_queue),
        REVIEW_QUEUE_COLUMNS,
    )
    write_qa_assertion_report(
        result.normalized_requests,
        output_path / "qa_assertion_report.md",
    )

    resolved_gold_path = Path(gold_path) if gold_path is not None else None
    if resolved_gold_path is not None and resolved_gold_path.exists():
        write_evaluation_report(
            output_path / "normalized_requests.json",
            resolved_gold_path,
            output_path / "evaluation_report.md",
        )
    return result


def main() -> None:
    """Run the CLI."""

    parser = argparse.ArgumentParser(prog="opsflow-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Normalize work requests")
    run_parser.add_argument("--input", required=True, help="CSV or JSONL input path")
    run_parser.add_argument("--config", default="config", help="Config directory")
    run_parser.add_argument("--output", default="outputs", help="Output directory")
    run_parser.add_argument(
        "--gold",
        default="data/labeled_requests.csv",
        help="Gold label CSV for evaluation report. Use an empty value to skip.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for MVP compatibility; external writes are not performed.",
    )
    run_parser.add_argument(
        "--enable-llm-assist",
        action="store_true",
        help="Enable OpenAI-backed LLM assist. Requires OPENAI_API_KEY in env or .env.",
    )
    run_parser.add_argument(
        "--prefer-dotenv",
        action="store_true",
        default=None,
        help=(
            "Let local .env override inherited environment values. "
            "Use only for local debugging."
        ),
    )

    args = parser.parse_args()
    if args.command == "run":
        gold_path = args.gold or None
        result = run_pipeline(
            args.input,
            args.config,
            args.output,
            gold_path,
            enable_llm_assist=args.enable_llm_assist,
            dotenv_override=args.prefer_dotenv,
        )
        print(
            "Processed "
            f"{len(result.normalized_requests)} requests. "
            f"Wrote outputs to {Path(args.output)}."
        )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, str | bool]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
