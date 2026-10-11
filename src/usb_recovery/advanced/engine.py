"""Multi-evidence ranking, iterative refinement, and method fusion (311, 314, 315)."""

from __future__ import annotations

from usb_recovery.carving.validators import run_validator
from usb_recovery.models import Candidate
from usb_recovery.reconstruct.matching import match_candidates


def _validate(candidate: Candidate) -> tuple[bool | None, list[str]]:
    content = candidate.extra.get("content")
    if not isinstance(content, (bytes, bytearray)):
        return None, []
    kind = candidate.file_type or candidate.extension
    return run_validator(kind, bytes(content))


def rank_multi_evidence(candidates: list[Candidate]) -> list[Candidate]:
    """Combine metadata, signatures, and structural validation into a ranked list (311)."""
    for item in candidates:
        evidence: list[str] = []
        score = float(item.confidence)
        if item.method in {"metadata", "existing"}:
            evidence.append("filesystem metadata")
            score += 8
        if item.method == "carved":
            evidence.append("file signature")
            score += 4
        if item.method == "orphan":
            evidence.append("orphan / contiguous heuristic")
            score -= 6
        ok, notes = _validate(item)
        if ok is True:
            evidence.append("structural validation passed")
            score += 15
        elif ok is False:
            evidence.append("structural validation failed")
            score -= 12
        evidence.extend(notes[:3])
        if item.sha256:
            evidence.append("content hash present")
            score += 3
        item.extra["evidence"] = evidence
        item.extra["multi_evidence_score"] = max(0.0, min(100.0, score))
        item.extra["multi_evidence_note"] = (
            "Combined rank is a heuristic, not a probability of successful recovery."
        )
    return sorted(
        candidates,
        key=lambda c: float(c.extra.get("multi_evidence_score", c.confidence)),
        reverse=True,
    )


def refine_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Re-score uncertain candidates once overlapping metadata is known (314)."""
    by_offset: dict[int, list[Candidate]] = {}
    for item in candidates:
        by_offset.setdefault(item.source_offset, []).append(item)
    for item in candidates:
        neighbours = by_offset.get(item.source_offset, [])
        meta = [n for n in neighbours if n.method in {"metadata", "existing"} and n.id != item.id]
        if item.method == "carved" and meta:
            item.confidence = min(100.0, item.confidence + 12)
            item.confidence_reasons.append(
                f"iterative refinement: metadata neighbour {meta[0].id} shares offset"
            )
            if not item.original_path and meta[0].original_path:
                item.original_path = meta[0].original_path
            item.extra["refined"] = True
        if item.status == "partial" and item.extra.get("content"):
            ok, _ = _validate(item)
            if ok:
                item.status = "carved"
                item.confidence = min(100.0, item.confidence + 8)
                item.confidence_reasons.append("iterative refinement: validator now passes")
    return rank_multi_evidence(candidates)


def fuse_methods(candidates: list[Candidate]) -> dict:
    """Keep metadata and carved findings, recording provenance of each (315)."""
    groups = match_candidates(candidates)
    fused = []
    used: set[str] = set()
    by_id = {c.id: c for c in candidates}
    for group in groups:
        ids = list(group.get("ids") or [])
        members = [by_id[i] for i in ids if i in by_id]
        if len(members) < 2:
            continue
        methods = sorted({m.method for m in members})
        if "metadata" in methods and "carved" in methods:
            fused.append(
                {
                    "ids": ids,
                    "methods": methods,
                    "kind": group.get("kind"),
                    "provenance": [
                        {
                            "id": m.id,
                            "method": m.method,
                            "offset": m.source_offset,
                            "name": m.name,
                        }
                        for m in members
                    ],
                    "note": "Both methods retained; fusion does not drop either finding.",
                }
            )
            used.update(ids)
    unmatched = [c.id for c in candidates if c.id not in used]
    return {
        "fused": fused,
        "unmatched_ids": unmatched,
        "count": len(fused),
        "note": "Cross-method fusion preserves provenance; it does not invent a single 'true' file.",
    }
