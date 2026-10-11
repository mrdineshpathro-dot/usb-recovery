"""Custom result columns (244)."""

from __future__ import annotations

from typing import Any

from usb_recovery.models import Candidate
from usb_recovery.util import human_size

AVAILABLE = [
    ("name", "Name"),
    ("original_path", "Original path"),
    ("size", "Size"),
    ("file_type", "Type"),
    ("method", "Method"),
    ("status", "Status"),
    ("confidence", "Score"),
    ("source_offset", "Offset"),
    ("sha256", "SHA-256"),
    ("extension", "Extension"),
    ("is_duplicate", "Duplicate"),
    ("is_fragmented", "Fragmented"),
]


def available_columns() -> list[tuple[str, str]]:
    return list(AVAILABLE)


def project_rows(candidates: list[Candidate], columns: list[str] | None = None) -> list[dict[str, Any]]:
    keys = columns or [k for k, _ in AVAILABLE[:7]]
    rows = []
    for item in candidates:
        row: dict[str, Any] = {}
        for key in keys:
            value = getattr(item, key, None)
            if key == "size" and isinstance(value, int):
                row[key] = human_size(value)
            else:
                row[key] = value
        row["_id"] = item.id
        rows.append(row)
    return rows
