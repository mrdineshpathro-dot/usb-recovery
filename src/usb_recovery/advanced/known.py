"""Known-content matching against hashes and byte sequences (318)."""

from __future__ import annotations

import hashlib

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import Candidate
from usb_recovery.util import sha256_bytes


def match_known_content(
    *,
    candidates: list[Candidate] | None = None,
    source: ReadOnlySource | None = None,
    hashes: list[str] | None = None,
    needles: list[bytes] | None = None,
    window: int = 1_048_576,
) -> dict:
    """Search candidates and/or a read-only source for known hashes or sequences."""
    want = {h.lower() for h in (hashes or []) if h}
    found_hash: list[dict] = []
    found_seq: list[dict] = []
    for item in candidates or []:
        digest = (item.sha256 or "").lower()
        content = item.extra.get("content")
        if not digest and isinstance(content, (bytes, bytearray)):
            digest = sha256_bytes(bytes(content))
        if digest and digest in want:
            found_hash.append({"id": item.id, "name": item.name, "sha256": digest, "where": "candidate"})
        if isinstance(content, (bytes, bytearray)):
            blob = bytes(content)
            for needle in needles or []:
                idx = blob.find(needle)
                if idx >= 0:
                    found_seq.append(
                        {
                            "id": item.id,
                            "name": item.name,
                            "offset": item.source_offset + idx,
                            "needle_len": len(needle),
                            "where": "candidate",
                        }
                    )
    if source is not None and needles:
        size = source.size
        step = max(len(max(needles, key=len)) - 1, 0)
        offset = 0
        while offset < size:
            chunk = source.read(offset, min(window, size - offset))
            if not chunk:
                break
            for needle in needles:
                start = 0
                while True:
                    idx = chunk.find(needle, start)
                    if idx < 0:
                        break
                    found_seq.append(
                        {
                            "offset": offset + idx,
                            "needle_len": len(needle),
                            "where": "source",
                        }
                    )
                    start = idx + 1
            if len(chunk) < window:
                break
            offset += window - step
            if len(found_seq) > 10_000:
                break
    if source is not None and want:
        # Hash the whole source only when it is small enough to be a file, not a device dump.
        if source.size <= 8 * 1024 * 1024:
            blob = source.read(0, source.size)
            digest = hashlib.sha256(blob).hexdigest()
            if digest in want:
                found_hash.append({"sha256": digest, "where": "source", "offset": 0})
    return {
        "hashes": found_hash,
        "sequences": found_seq,
        "note": "A hash/sequence hit locates bytes; it does not reconstruct a deleted file.",
    }
