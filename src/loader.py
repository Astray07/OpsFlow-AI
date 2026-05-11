"""Input loading utilities."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schema import RawRequest


SUPPORTED_SUFFIXES = {".csv", ".jsonl", ".ndjson"}
REQUIRED_COLUMNS = {"request_id", "raw_text"}
RAW_REQUEST_FIELDS = {"request_id", "requester", "channel", "raw_text", "created_at"}


def load_requests(path: str | Path) -> list[RawRequest]:
    """Load requests from a supported input file."""

    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return load_csv_requests(input_path)
    if suffix in {".jsonl", ".ndjson"}:
        return load_jsonl_requests(input_path)

    supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
    raise ValueError(f"Unsupported input file extension '{suffix}'. Supported: {supported}")


def load_csv_requests(path: str | Path) -> list[RawRequest]:
    """Load CSV rows into ``RawRequest`` models."""

    input_path = Path(path)
    with input_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"CSV file has no header row: {input_path}")

        missing_columns = REQUIRED_COLUMNS - set(fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV file is missing required columns: {missing}")

        requests: list[RawRequest] = []
        for row_number, row in enumerate(reader, start=2):
            requests.append(_row_to_raw_request(row, input_path, row_number))
        return requests


def load_jsonl_requests(path: str | Path) -> list[RawRequest]:
    """Load JSONL rows into ``RawRequest`` models."""

    input_path = Path(path)
    requests: list[RawRequest] = []
    with input_path.open(encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {input_path}:{line_number}: {exc.msg}"
                ) from exc

            if not isinstance(payload, Mapping):
                raise ValueError(
                    f"Invalid JSONL row at {input_path}:{line_number}: expected object"
                )

            requests.append(_row_to_raw_request(payload, input_path, line_number))
    return requests


def _row_to_raw_request(
    row: Mapping[str | None, Any], source_path: Path, row_number: int
) -> RawRequest:
    cleaned_row = {
        key: _clean_value(value)
        for key, value in row.items()
        if key is not None
    }

    metadata = {
        key: value
        for key, value in cleaned_row.items()
        if key not in RAW_REQUEST_FIELDS and value is not None
    }

    payload = {
        "request_id": cleaned_row.get("request_id"),
        "raw_text": cleaned_row.get("raw_text"),
        "requester": cleaned_row.get("requester") or cleaned_row.get("user_id"),
        "channel": cleaned_row.get("channel"),
        "created_at": cleaned_row.get("created_at"),
        "metadata": metadata,
    }

    try:
        return RawRequest(**payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid request at {source_path}:{row_number}: {exc}") from exc


def _clean_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value
