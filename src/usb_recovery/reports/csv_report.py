from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

FIELDS = [
    "id",
    "name",
    "original_path",
    "size",
    "file_type",
    "mime",
    "method",
    "status",
    "confidence",
    "source_offset",
    "sha256",
]


def write_csv_report(path: Path, candidates: list[dict[str, Any]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in candidates:
            writer.writerow({k: item.get(k, "") for k in FIELDS})
    return path
