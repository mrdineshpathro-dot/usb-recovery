"""Unicode filename reconstruction (275)."""

from __future__ import annotations

import unicodedata


def reconstruct_filename(name: str | bytes, encodings: tuple[str, ...] = ("utf-8", "utf-16le", "cp437", "latin-1")) -> dict:
    raw: bytes
    if isinstance(name, bytes):
        raw = name
        original = None
    else:
        original = name
        raw = name.encode("utf-8", errors="surrogateescape")
    candidates: list[str] = []
    if original:
        candidates.append(unicodedata.normalize("NFC", original))
        candidates.append(unicodedata.normalize("NFD", original))
    for enc in encodings:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        candidates.append(unicodedata.normalize("NFC", text))
    # unique preserving order
    seen: list[str] = []
    for item in candidates:
        cleaned = "".join(ch for ch in item if ch == " " or unicodedata.category(ch)[0] != "C")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    best = seen[0] if seen else (original or "")
    return {
        "preferred": best,
        "alternates": seen[1:8],
        "had_combining": any(unicodedata.combining(ch) for ch in (original or best)),
    }
