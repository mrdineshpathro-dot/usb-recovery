"""Candidate timeline from trustworthy timestamps and offsets (220)."""

from __future__ import annotations

from usb_recovery.models import Candidate


def candidate_timeline(candidates: list[Candidate]) -> list[dict]:
    rows: list[dict] = []
    for item in candidates:
        ts = item.timestamps.modified or item.timestamps.created
        trustworthy = bool(ts) and item.method in {"metadata", "existing"}
        rows.append(
            {
                "id": item.id,
                "name": item.name,
                "timestamp": ts,
                "trustworthy": trustworthy,
                "offset": item.source_offset,
                "method": item.method,
                "status": item.status,
            }
        )
    rows.sort(key=lambda r: (r["timestamp"] is None, r["timestamp"] or "", r["offset"]))
    return rows
