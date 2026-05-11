import csv
from pathlib import Path

from src.normalizer import normalize_requests
from src.schema import RawRequest


def test_edge_case_expected_handling_matches_pipeline_decisions() -> None:
    with Path("data/edge_cases.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    raw_requests = [
        RawRequest(
            request_id=row["request_id"],
            raw_text=row["raw_text"],
            channel="edge_case",
            metadata={"edge_case_type": row["edge_case_type"]},
        )
        for row in rows
    ]
    result = normalize_requests(raw_requests, "config")

    actual_by_id = {
        request.request_id: request.automation_decision.value
        for request in result.normalized_requests
    }

    assert len(rows) == 15
    for row in rows:
        assert actual_by_id[row["request_id"]] == row["expected_handling"]
