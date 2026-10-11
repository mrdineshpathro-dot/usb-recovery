"""OOXML relationship and required-part validator (335)."""

from __future__ import annotations

import io
import zipfile


def validate_ooxml_relationships(data: bytes) -> dict:
    """Check [Content_Types].xml, _rels, and document parts inside a ZIP/OOXML buffer."""
    if not data.startswith(b"PK"):
        return {"ok": False, "reason": "not a ZIP/OOXML container"}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"ok": False, "reason": "ZIP central directory unreadable"}
    names = set(zf.namelist())
    has_ct = "[Content_Types].xml" in names
    has_rels = "_rels/.rels" in names
    kind = "zip"
    required: list[str] = []
    if any(n.startswith("word/") for n in names):
        kind = "docx"
        required = ["word/document.xml"]
    elif any(n.startswith("xl/") for n in names):
        kind = "xlsx"
        required = ["xl/workbook.xml"]
    elif any(n.startswith("ppt/") for n in names):
        kind = "pptx"
        required = ["ppt/presentation.xml"]
    missing = [p for p in required if p not in names]
    rels_ok = False
    if has_rels:
        try:
            rels = zf.read("_rels/.rels")
            rels_ok = b"Relationship" in rels
        except Exception:
            rels_ok = False
    return {
        "ok": has_ct and has_rels and not missing,
        "kind": kind,
        "has_content_types": has_ct,
        "has_rels": has_rels,
        "rels_ok": rels_ok,
        "missing_parts": missing,
        "parts": sorted(names)[:64],
        "note": "Relationship checks run on an isolated buffer. Broken parts are not repaired in place.",
    }
