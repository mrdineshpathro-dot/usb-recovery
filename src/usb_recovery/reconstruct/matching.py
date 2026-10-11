"""Cross-scan candidate matching (feature 211)."""

from __future__ import annotations

from usb_recovery.models import Candidate


def _overlap(a: Candidate, b: Candidate) -> int:
    a1, a2 = a.source_offset, a.source_offset + max(a.size, 1)
    b1, b2 = b.source_offset, b.source_offset + max(b.size, 1)
    return max(0, min(a2, b2) - max(a1, b1))


def match_candidates(candidates: list[Candidate]) -> list[dict]:
    """Group related findings from metadata vs carving without dropping either."""
    groups: list[dict] = []
    used: set[str] = set()
    by_hash: dict[str, list[Candidate]] = {}
    for item in candidates:
        if item.sha256:
            by_hash.setdefault(item.sha256, []).append(item)
    for digest, items in by_hash.items():
        if len(items) < 2:
            continue
        ids = [c.id for c in items]
        used.update(ids)
        groups.append(
            {
                "kind": "identical-hash",
                "sha256": digest,
                "ids": ids,
                "names": [c.name for c in items],
                "methods": sorted({c.method for c in items}),
            }
        )
    remaining = [c for c in candidates if c.id not in used]
    remaining.sort(key=lambda c: c.source_offset)
    for i, a in enumerate(remaining):
        for b in remaining[i + 1 :]:
            if b.source_offset > a.source_offset + max(a.size, 1) + 4096:
                break
            overlap = _overlap(a, b)
            if overlap <= 0:
                continue
            if a.method == b.method and a.name == b.name:
                continue
            groups.append(
                {
                    "kind": "offset-overlap",
                    "ids": [a.id, b.id],
                    "names": [a.name, b.name],
                    "methods": [a.method, b.method],
                    "overlap_bytes": overlap,
                    "offsets": [a.source_offset, b.source_offset],
                }
            )
            used.add(a.id)
            used.add(b.id)
    return groups
