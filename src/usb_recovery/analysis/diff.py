"""Multi-method candidate comparison / diff viewer (274, 283)."""

from __future__ import annotations

from usb_recovery.models import Candidate
from usb_recovery.reconstruct.matching import match_candidates


def diff_candidates(a: Candidate, b: Candidate) -> dict:
    keys = ("name", "size", "method", "status", "source_offset", "sha256", "confidence", "original_path")
    changes = {}
    for key in keys:
        va, vb = getattr(a, key), getattr(b, key)
        if va != vb:
            changes[key] = {"a": va, "b": vb}
    same_hash = bool(a.sha256 and a.sha256 == b.sha256)
    return {
        "ids": [a.id, b.id],
        "same_hash": same_hash,
        "changes": changes,
        "methods": [a.method, b.method],
    }


def compare_methods_in_session(candidates: list[Candidate]) -> list[dict]:
    groups = match_candidates(candidates)
    out = []
    by_id = {c.id: c for c in candidates}
    for g in groups:
        ids = g.get("ids") or []
        if len(ids) >= 2 and ids[0] in by_id and ids[1] in by_id:
            out.append({**g, "diff": diff_candidates(by_id[ids[0]], by_id[ids[1]])})
    return out
