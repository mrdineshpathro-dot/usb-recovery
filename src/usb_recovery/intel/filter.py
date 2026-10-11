"""Format-aware false-positive filter (345)."""

from __future__ import annotations

from usb_recovery.carving.validators import run_validator
from usb_recovery.models import Candidate


def filter_false_positives(candidates: list[Candidate], *, drop: bool = False) -> dict:
    """Reject likely false detections using structural validators."""
    kept: list[Candidate] = []
    rejected: list[dict] = []
    for item in candidates:
        content = item.extra.get("content")
        if not isinstance(content, (bytes, bytearray)):
            kept.append(item)
            continue
        kind = item.file_type or item.extension
        ok, notes = run_validator(kind, bytes(content))
        if ok is False and item.method == "carved" and item.confidence < 50:
            rejected.append({"id": item.id, "name": item.name, "notes": notes})
            item.notes.append("false-positive filter: structural check failed")
            if not drop:
                item.confidence = min(item.confidence, 15)
                kept.append(item)
            continue
        kept.append(item)
    return {
        "kept": kept,
        "rejected": rejected,
        "dropped": drop,
        "note": "Filter uses format validators. It never deletes source data.",
    }
