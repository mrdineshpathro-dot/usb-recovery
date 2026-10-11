"""Partial-file region view and fragment explorer (212, 213)."""

from __future__ import annotations

from usb_recovery.models import ByteRange, Candidate


def regions_for(candidate: Candidate) -> list[ByteRange]:
    extra = candidate.extra or {}
    stored = extra.get("regions")
    if isinstance(stored, list) and stored:
        out: list[ByteRange] = []
        for item in stored:
            if isinstance(item, ByteRange):
                out.append(item)
            elif isinstance(item, dict):
                out.append(
                    ByteRange(
                        int(item.get("start", 0)),
                        int(item.get("end", 0)),
                        item.get("kind", "recovered"),  # type: ignore[arg-type]
                    )
                )
        if out:
            return out
    content = extra.get("content")
    size = candidate.size or (len(content) if isinstance(content, (bytes, bytearray)) else 0)
    if isinstance(content, (bytes, bytearray)) and size:
        have = min(len(content), size)
        ranges = [ByteRange(0, have, "recovered")]
        if have < size:
            ranges.append(ByteRange(have, size, "missing"))
        return ranges
    if candidate.status in {"partial", "unreadable"}:
        return [ByteRange(0, max(size, 1), "uncertain")]
    if size:
        return [ByteRange(0, size, "recovered")]
    return []


def fragment_groups(candidates: list[Candidate], proximity: int = 1_048_576) -> list[dict]:
    """Cluster carved/orphan fragments that sit near each other on the source."""
    frags = [c for c in candidates if c.method in {"carved", "orphan"} or c.is_fragmented]
    frags.sort(key=lambda c: (c.file_type, c.source_offset))
    groups: list[dict] = []
    current: list[Candidate] = []
    for item in frags:
        if (
            current
            and item.file_type == current[-1].file_type
            and item.source_offset - (current[-1].source_offset + current[-1].size) <= proximity
        ):
            current.append(item)
            continue
        if len(current) >= 2:
            groups.append(_pack(current))
        current = [item]
    if len(current) >= 2:
        groups.append(_pack(current))
    return groups


def _pack(items: list[Candidate]) -> dict:
    return {
        "file_type": items[0].file_type,
        "count": len(items),
        "ids": [c.id for c in items],
        "offsets": [c.source_offset for c in items],
        "note": (
            "Proximity does not prove these fragments belong to one file. "
            "Heuristic grouping only."
        ),
    }
