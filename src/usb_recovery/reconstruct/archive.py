"""Archive salvage and embedded-content detection (216, 219)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable

from usb_recovery.carving.signatures import FileSignature, load_signatures


def salvage_zip(data: bytes) -> dict:
    """Extract local-file headers even when the EOCD is missing."""
    entries: list[dict] = []
    offset = 0
    while True:
        idx = data.find(b"PK\x03\x04", offset)
        if idx < 0:
            break
        if idx + 30 > len(data):
            break
        (
            _ver,
            flags,
            method,
            _time,
            _date,
            crc,
            comp,
            uncomp,
            name_len,
            extra_len,
        ) = struct.unpack_from("<HHHHHIIIHH", data, idx + 4)
        name_start = idx + 30
        name_end = name_start + name_len
        extra_end = name_end + extra_len
        if name_end > len(data):
            entries.append({"name": None, "offset": idx, "truncated": True})
            break
        name = data[name_start:name_end].decode("utf-8", errors="replace")
        data_start = extra_end
        data_end = data_start + comp if comp < 0xFFFFFFFF else data_start
        entries.append(
            {
                "name": name,
                "offset": idx,
                "method": method,
                "flags": flags,
                "crc": crc,
                "compressed": comp,
                "uncompressed": uncomp,
                "truncated": data_end > len(data),
                "payload_offset": data_start,
            }
        )
        offset = max(data_end, idx + 4)
        if len(entries) > 10_000:
            break
    eocd = data.rfind(b"PK\x05\x06")
    return {
        "entries": entries,
        "count": len(entries),
        "eocd": eocd >= 0,
        "salvageable": bool(entries),
        "note": "Local headers parsed without trusting a missing central directory.",
    }


def scan_embedded(data: bytes, *, max_hits: int = 32) -> list[dict]:
    """Find nested file signatures inside a buffer (documents/archives)."""
    _, sigs = load_signatures()
    hits: list[dict] = []
    for sig in sigs:
        start = 0
        while len(hits) < max_hits:
            idx = data.find(sig.header, start)
            if idx < 0:
                break
            abs_off = idx - sig.header_offset
            if abs_off > 0:  # skip the container's own header at 0
                hits.append(
                    {
                        "signature_id": sig.id,
                        "offset": abs_off,
                        "name": sig.name,
                        "mime": sig.mime,
                    }
                )
            start = idx + max(1, len(sig.header))
    return hits


def salvage_zip_file(path: str | Path) -> dict:
    return salvage_zip(Path(path).read_bytes())
