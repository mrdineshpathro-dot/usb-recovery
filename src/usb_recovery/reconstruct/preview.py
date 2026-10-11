"""Safe preview of recovered portions without executing content (218)."""

from __future__ import annotations

from usb_recovery.models import Candidate
from usb_recovery.reconstruct.regions import regions_for
from usb_recovery.util import decode_ascii


def preview_partial(candidate: Candidate, *, limit: int = 4096) -> dict:
    content = candidate.extra.get("content") if isinstance(candidate.extra, dict) else None
    blob = bytes(content[:limit]) if isinstance(content, (bytes, bytearray)) else b""
    regions = [
        {"start": r.start, "end": r.end, "kind": r.kind, "length": r.length} for r in regions_for(candidate)
    ]
    kind = "hex"
    text = ""
    if candidate.mime.startswith("text/") or candidate.file_type in {"txt", "csv", "log"}:
        kind = "text"
        text = blob.decode("utf-8", errors="replace")
    elif candidate.mime.startswith("image/"):
        kind = "image-bytes"
        text = f"{len(blob)} buffered image bytes (not executed)"
    else:
        text = decode_ascii(blob[:512])
    recovered = sum(r["length"] for r in regions if r["kind"] == "recovered")
    missing = sum(r["length"] for r in regions if r["kind"] == "missing")
    return {
        "id": candidate.id,
        "name": candidate.name,
        "kind": kind,
        "text": text,
        "bytes_shown": len(blob),
        "regions": regions,
        "recovered_bytes": recovered,
        "missing_bytes": missing,
        "executed": False,
    }
