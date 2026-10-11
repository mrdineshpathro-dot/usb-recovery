"""Feature readiness dashboard data (310)."""

from __future__ import annotations

import re
from pathlib import Path

STATUS_RANK = {"done": 3, "partial": 2, "stub": 1, "unsupported": 0}


def feature_readiness(features_md: Path | None = None) -> dict:
    path = features_md or Path(__file__).resolve().parents[3] / "docs" / "FEATURES.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    rows = []
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d{3})\s*\|\s*([^|]+)\|\s*(done|partial|stub|unsupported)\s*\|", line)
        if not m:
            continue
        rows.append(
            {
                "id": m.group(1),
                "name": m.group(2).strip(),
                "status": m.group(3),
            }
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "total": len(rows),
        "counts": counts,
        "features": rows,
        "source": str(path),
    }
