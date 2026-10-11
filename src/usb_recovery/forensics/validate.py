"""Independent validation engine (354) — separate from reconstruction."""

from __future__ import annotations

from usb_recovery.carving.validators import run_validator
from usb_recovery.models import Candidate
from usb_recovery.reconstruct.documents import validate_document


def independent_validate(candidates: list[Candidate]) -> list[dict]:
    """Validate recovered/carved bytes with the shared validators, not the reconstructor."""
    out = []
    for item in candidates:
        content = item.extra.get("content")
        data = bytes(content) if isinstance(content, (bytes, bytearray)) else b""
        kind = item.file_type or item.extension
        ok, notes = run_validator(kind, data) if data else (None, ["no payload in extra.content"])
        doc = validate_document(data, kind) if data else None
        out.append(
            {
                "id": item.id,
                "name": item.name,
                "claimed_type": kind,
                "ok": ok,
                "notes": notes,
                "document": doc,
                "engine": "carving.validators",
                "independent_of": item.method,
            }
        )
    return out
