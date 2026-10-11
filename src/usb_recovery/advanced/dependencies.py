"""Partial-file dependency analysis (319)."""

from __future__ import annotations

from usb_recovery.carving.validators import run_validator
from usb_recovery.models import Candidate


def missing_sections(data: bytes, file_type: str) -> dict:
    """Identify which missing pieces prevent a candidate from validating."""
    kind = (file_type or "").lower()
    missing: list[str] = []
    present: list[str] = []
    if kind == "jpeg":
        if data.startswith(b"\xff\xd8"):
            present.append("SOI")
        else:
            missing.append("SOI (FFD8)")
        if b"\xff\xda" in data:
            present.append("SOS")
        else:
            missing.append("SOS (start of scan)")
        if b"\xff\xd9" in data:
            present.append("EOI")
        else:
            missing.append("EOI (FFD9) — truncated image")
    elif kind == "png":
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            present.append("signature")
        else:
            missing.append("PNG signature")
        if b"IHDR" in data:
            present.append("IHDR")
        else:
            missing.append("IHDR")
        if b"IDAT" in data:
            present.append("IDAT")
        else:
            missing.append("IDAT image data")
        if b"IEND" in data:
            present.append("IEND")
        else:
            missing.append("IEND")
    elif kind == "pdf":
        if data.startswith(b"%PDF-"):
            present.append("header")
        else:
            missing.append("%PDF- header")
        if b"xref" in data or b"/XRef" in data:
            present.append("xref")
        else:
            missing.append("xref / cross-reference table")
        if b"%%EOF" in data:
            present.append("%%EOF")
        else:
            missing.append("%%EOF")
    elif kind in {"zip", "docx", "xlsx", "pptx"}:
        if data.startswith(b"PK\x03\x04"):
            present.append("local-file-header")
        else:
            missing.append("ZIP local file header")
        if b"PK\x01\x02" in data:
            present.append("central-directory")
        else:
            missing.append("central directory")
        if b"PK\x05\x06" in data:
            present.append("EOCD")
        else:
            missing.append("end of central directory")
    elif kind == "mp4":
        if len(data) >= 8 and data[4:8] == b"ftyp":
            present.append("ftyp")
        else:
            missing.append("ftyp")
        if b"moov" in data:
            present.append("moov")
        else:
            missing.append("moov index — playback will fail without it")
        if b"mdat" in data:
            present.append("mdat")
        else:
            missing.append("mdat media data")
    elif kind == "sqlite":
        if data.startswith(b"SQLite format 3\x00"):
            present.append("header")
        else:
            missing.append("SQLite header")
    else:
        missing.append("no format-specific dependency map")
    ok, notes = run_validator(kind, data) if kind else (None, [])
    return {
        "file_type": kind,
        "present": present,
        "missing": missing,
        "validates": ok,
        "validator_notes": notes,
        "complete": not missing,
        "note": "Missing sections explain why validation fails; they are not recovered automatically.",
    }


def candidate_dependencies(candidate: Candidate) -> dict:
    content = candidate.extra.get("content")
    data = bytes(content) if isinstance(content, (bytes, bytearray)) else b""
    result = missing_sections(data, candidate.file_type or candidate.extension)
    result["id"] = candidate.id
    result["name"] = candidate.name
    return result
