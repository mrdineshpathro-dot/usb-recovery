"""Automated recovery quality scorecard (350)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from usb_recovery.devtools.validator import validate_expected
from usb_recovery.models import Candidate


def quality_scorecard(
    recovered: str | Path,
    expected: list[dict],
    *,
    candidates: list[Candidate] | None = None,
) -> dict:
    """Measure success against known test files and report limits by type."""
    result = validate_expected(Path(recovered), expected)
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"expected": 0, "found": 0})
    found_names = {p.name.lower() for p in Path(recovered).iterdir()} if Path(recovered).is_dir() else set()
    for item in expected:
        name = (item.get("name") or "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "bin"
        by_type[ext]["expected"] += 1
        if name.lower() in found_names:
            by_type[ext]["found"] += 1
    limits = []
    if candidates:
        partial = sum(1 for c in candidates if c.status == "partial")
        if partial:
            limits.append(f"{partial} partial candidates — truncated payloads")
        carved = sum(1 for c in candidates if c.method == "carved")
        if carved:
            limits.append("carved files usually lack original names")
    return {
        "ok": result.get("ok"),
        "validation": result,
        "by_type": dict(by_type),
        "limitations": limits
        + [
            "Success on a synthetic corpus does not predict success on a worn USB stick.",
            "Fragmented and TRIM'd data cannot be reconstructed from thin air.",
        ],
    }
