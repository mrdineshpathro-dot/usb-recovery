"""Scan-result anomaly detector (344)."""

from __future__ import annotations

from collections import Counter

from usb_recovery.models import Candidate


def detect_scan_anomalies(
    candidates: list[Candidate],
    *,
    read_errors: int = 0,
    source_size: int = 0,
) -> dict:
    types = Counter(c.file_type or "unknown" for c in candidates)
    methods = Counter(c.method for c in candidates)
    flags: list[str] = []
    if candidates and types.most_common(1)[0][1] / len(candidates) > 0.9:
        flags.append(f"one file type dominates ({types.most_common(1)[0][0]})")
    if read_errors > 0:
        flags.append(f"{read_errors} read errors recorded")
    carved = methods.get("carved", 0)
    if carved and carved == len(candidates) and len(candidates) > 20:
        flags.append("only carved hits — metadata may be missing or filesystem unknown")
    if source_size and candidates:
        span = max(c.source_offset + max(c.size, 1) for c in candidates) - min(c.source_offset for c in candidates)
        if span > 0 and span < source_size * 0.01 and len(candidates) > 10:
            flags.append("candidates clustered in <1% of the source")
    offsets = [c.source_offset for c in candidates]
    if len(offsets) >= 4 and len(set(offsets)) == 1:
        flags.append("all candidates share the same source offset")
    low = sum(1 for c in candidates if c.confidence < 30)
    if candidates and low / len(candidates) > 0.8:
        flags.append("most scores are in the uncertain band")
    return {
        "flags": flags,
        "type_histogram": dict(types),
        "method_histogram": dict(methods),
        "read_errors": read_errors,
        "anomalous": bool(flags),
        "note": "Anomalies are unusual distributions, not proof of tampering or of recovery failure.",
    }
