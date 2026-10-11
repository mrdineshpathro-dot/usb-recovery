"""PDF cross-reference recovery on an isolated copy (334)."""

from __future__ import annotations

import re


_OBJ = re.compile(rb"(\d+)\s+0\s+obj")


def recover_pdf_xref(data: bytes) -> dict:
    """Rebuild a simple xref table on a copy when the original is missing."""
    objects = [(int(m.group(1)), m.start()) for m in _OBJ.finditer(data)]
    has_xref = b"xref" in data or b"/Type /XRef" in data or b"/Type/XRef" in data
    has_eof = b"%%EOF" in data
    if has_xref and has_eof:
        return {
            "repaired": False,
            "ok": True,
            "objects": len(objects),
            "copy": data,
            "note": "xref and %%EOF already present.",
        }
    if not data.startswith(b"%PDF-") and b"%PDF-" not in data[:1024]:
        return {"repaired": False, "ok": False, "reason": "not a PDF header", "objects": 0}
    # Build a classic xref for the isolated copy.
    lines = [b"xref\n", f"0 {len(objects) + 1}\n".encode(), b"0000000000 65535 f \n"]
    for _num, pos in objects:
        lines.append(f"{pos:010d} 00000 n \n".encode())
    xref = b"".join(lines)
    start = len(data) if not data.endswith(b"\n") else len(data)
    body = data if data.endswith(b"\n") else data + b"\n"
    trailer = (
        b"trailer<< /Size "
        + str(len(objects) + 1).encode()
        + b" >>\nstartxref\n"
        + str(len(body)).encode()
        + b"\n%%EOF\n"
    )
    copy = body + xref + trailer
    return {
        "repaired": True,
        "ok": bool(objects),
        "objects": len(objects),
        "copy": copy,
        "startxref": start,
        "note": "xref rebuilt on an isolated copy only. Object streams / compressed xref are not reconstructed.",
    }
