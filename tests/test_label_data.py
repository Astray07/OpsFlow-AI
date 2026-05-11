import csv
from pathlib import Path

from src.schema import AutomationDecision, Priority, RequestType, RiskLevel, Team


DATA_DIR = Path("data")


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_sample_and_label_request_ids_match() -> None:
    samples = read_csv("sample_requests.csv")
    labels = read_csv("labeled_requests.csv")

    sample_ids = {row["request_id"] for row in samples}
    label_ids = {row["request_id"] for row in labels}

    assert len(samples) == 30
    assert len(labels) == 30
    assert sample_ids == label_ids


def test_label_values_match_schema_enums() -> None:
    labels = read_csv("labeled_requests.csv")

    request_types = {item.value for item in RequestType}
    teams = {item.value for item in Team}
    priorities = {item.value for item in Priority}
    decisions = {item.value for item in AutomationDecision}
    risk_levels = {item.value for item in RiskLevel}

    for row in labels:
        assert row["expected_request_type"] in request_types
        assert row["expected_target_team"] in teams
        assert row["expected_priority"] in priorities
        assert row["expected_automation_decision"] in decisions
        assert row["expected_risk_level"] in risk_levels


def test_label_dataset_covers_core_decisions_and_request_types() -> None:
    labels = read_csv("labeled_requests.csv")

    covered_types = {row["expected_request_type"] for row in labels}
    covered_decisions = {row["expected_automation_decision"] for row in labels}

    assert covered_types == {item.value for item in RequestType}
    assert covered_decisions == {item.value for item in AutomationDecision}


def test_edge_cases_have_supported_expected_handling_values() -> None:
    edge_cases = read_csv("edge_cases.csv")
    decisions = {item.value for item in AutomationDecision}

    assert len(edge_cases) == 15
    for row in edge_cases:
        assert row["expected_handling"] in decisions


def test_external_seed_requests_have_public_sources() -> None:
    seeds = read_csv("external_seed_requests.csv")

    assert len(seeds) >= 5
    for row in seeds:
        assert row["seed_id"].startswith("EXT-")
        assert row["source_url"].startswith("https://github.com/")
        assert row["collected_at"] == "2026-05-11"
        assert row["raw_text_pattern"].strip()
        assert "paraphrase" in row["notes"]


def test_external_seed_samples_and_labels_match() -> None:
    samples = read_csv("external_seed_samples.csv")
    labels = read_csv("external_seed_labeled_requests.csv")

    sample_ids = {row["request_id"] for row in samples}
    label_ids = {row["request_id"] for row in labels}
    decisions = {item.value for item in AutomationDecision}

    assert len(samples) == 8
    assert len(labels) == 8
    assert sample_ids == label_ids
    assert {row["source"] for row in samples} == {"external_seed"}
    for row in labels:
        assert row["source_type"] == "external_seed"
        assert row["expected_automation_decision"] in decisions
