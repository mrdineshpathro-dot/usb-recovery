"""Explainable heuristic confidence scores. These are not probabilities."""

from __future__ import annotations

from usb_recovery.constants import CONFIDENCE_BANDS
from usb_recovery.models import Candidate


def band_for(score: float) -> tuple[str, str]:
    for threshold, name, explanation in CONFIDENCE_BANDS:
        if score >= threshold:
            return name, explanation
    return "uncertain", CONFIDENCE_BANDS[-1][2]


def annotate(candidate: Candidate) -> Candidate:
    name, explanation = band_for(candidate.confidence)
    note = f"score {candidate.confidence:.0f}/100 is a heuristic '{name}' band, not a probability"
    if note not in candidate.confidence_reasons:
        candidate.confidence_reasons.append(note)
    candidate.extra.setdefault("confidence_band", name)
    candidate.extra.setdefault("confidence_band_meaning", explanation)
    return candidate


def deduplicate(candidates: list[Candidate]) -> list[Candidate]:
    """Mark identical SHA-256 payloads; keep every distinct filename."""
    seen: dict[str, str] = {}
    for item in candidates:
        if not item.sha256:
            continue
        if item.sha256 in seen:
            item.is_duplicate = True
            item.notes.append(f"same content as {seen[item.sha256]}")
        else:
            seen[item.sha256] = item.id
    return candidates
