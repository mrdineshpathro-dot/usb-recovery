"""Metadata privacy review (feature 253)."""

from __future__ import annotations

import re

from usb_recovery.models import Candidate

GPS_HINT = re.compile(rb"\x02\x02\x00\x00|\x00\x02\x00\x02")  # rough EXIF GPS IFD
AUTHOR_HINTS = (b"Author", b"creator", b"<dc:creator", b"Last Modified By")


def review_privacy(candidate: Candidate, data: bytes | None = None) -> dict:
    blob = data
    if blob is None and isinstance(candidate.extra.get("content"), (bytes, bytearray)):
        blob = bytes(candidate.extra["content"][:64_000])
    blob = blob or b""
    findings: list[str] = []
    if GPS_HINT.search(blob) or b"GPS" in blob[:4096]:
        findings.append("Possible GPS / location EXIF in this buffer")
    for token in AUTHOR_HINTS:
        if token in blob:
            findings.append(f"Possible author/creator metadata ({token.decode('latin1')})")
            break
    if candidate.original_path and any(p in candidate.original_path.lower() for p in ("secret", "password", "private")):
        findings.append("Original path contains a privacy-sensitive word")
    return {
        "id": candidate.id,
        "name": candidate.name,
        "findings": findings,
        "sensitive": bool(findings),
        "note": "Heuristic review of buffered bytes only. Sharing recovered files may still leak metadata.",
    }
