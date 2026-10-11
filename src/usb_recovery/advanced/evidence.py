"""Recovery evidence explorer (320)."""

from __future__ import annotations

from usb_recovery.advanced.dependencies import candidate_dependencies
from usb_recovery.advanced.engine import fuse_methods, rank_multi_evidence
from usb_recovery.advanced.fragments import boundary_confidence, fragment_graph
from usb_recovery.models import Candidate


def explain_evidence(candidates: list[Candidate]) -> dict:
    """Explain which sectors, metadata, and validators support each decision."""
    ranked = rank_multi_evidence(list(candidates))
    items = []
    for item in ranked:
        content = item.extra.get("content")
        blob = bytes(content) if isinstance(content, (bytes, bytearray)) else b""
        items.append(
            {
                "id": item.id,
                "name": item.name,
                "method": item.method,
                "status": item.status,
                "offset": item.source_offset,
                "size": item.size,
                "confidence": item.confidence,
                "multi_evidence_score": item.extra.get("multi_evidence_score"),
                "evidence": item.extra.get("evidence") or [],
                "reasons": list(item.confidence_reasons),
                "boundary": boundary_confidence(blob, item.file_type) if blob else None,
                "dependencies": candidate_dependencies(item) if blob else None,
                "sectors": {
                    "start": item.source_offset // 512,
                    "count": max(1, (item.size + 511) // 512),
                },
            }
        )
    return {
        "candidates": items,
        "graph": fragment_graph(ranked),
        "fusion": fuse_methods(ranked),
        "note": (
            "Evidence listings explain a heuristic decision. "
            "They do not guarantee that the original file can be recovered."
        ),
    }
