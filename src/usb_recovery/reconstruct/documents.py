"""Document structure validation beyond extensions (feature 217)."""

from __future__ import annotations

from usb_recovery.carving.validators import validate_pdf, validate_zip


def validate_document(data: bytes, claimed_type: str = "") -> dict:
    kind = (claimed_type or "").lower().lstrip(".")
    notes: list[str] = []
    ok = False
    detected = "unknown"
    if data.startswith(b"%PDF-"):
        detected = "pdf"
        ok, notes = validate_pdf(data)
    elif data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06"):
        ok, notes = validate_zip(data)
        sample = data[: min(len(data), 2_000_000)]
        if b"word/" in sample:
            detected = "docx"
        elif b"xl/" in sample:
            detected = "xlsx"
        elif b"ppt/" in sample:
            detected = "pptx"
        else:
            detected = "zip"
    elif data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        detected = "ole"
        ok = len(data) >= 512
        notes = ["OLE compound header present; streams not fully parsed"]
    elif data.startswith(b"{\\rtf"):
        detected = "rtf"
        ok = True
        notes = ["RTF header"]
    mismatch = bool(kind and detected != "unknown" and kind not in {detected, "zip", "doc", "xls", "ppt"})
    if kind in {"doc", "xls", "ppt"} and detected == "ole":
        mismatch = False
    if kind in {"docx", "xlsx", "pptx"} and detected == kind:
        mismatch = False
    return {
        "ok": ok,
        "detected": detected,
        "claimed": kind or None,
        "extension_mismatch": mismatch,
        "notes": notes,
    }
