"""ZIP central-directory reconstruction on an isolated copy (333)."""

from __future__ import annotations

import struct

from usb_recovery.reconstruct.archive import salvage_zip


def reconstruct_zip_directory(data: bytes) -> dict:
    """Rebuild a central directory from local headers when EOCD is missing."""
    salv = salvage_zip(data)
    if salv.get("eocd"):
        return {
            "repaired": False,
            "ok": True,
            "entries": salv["count"],
            "copy": data,
            "note": "EOCD already present; no rewrite.",
        }
    centrals = []
    for entry in salv.get("entries") or []:
        name = (entry.get("name") or "").encode("utf-8")
        if not name and entry.get("truncated"):
            continue
        crc = int(entry.get("crc") or 0)
        comp = int(entry.get("compressed") or 0)
        uncomp = int(entry.get("uncompressed") or 0)
        local_off = int(entry.get("offset") or 0)
        central = (
            b"PK\x01\x02"
            + struct.pack(
                "<HHHHHHIIIHHHHHII",
                20,
                20,
                int(entry.get("flags") or 0),
                int(entry.get("method") or 0),
                0,
                0,
                crc,
                comp,
                uncomp,
                len(name),
                0,
                0,
                0,
                0,
                0,
                local_off,
            )
            + name
        )
        centrals.append(central)
    cd = b"".join(centrals)
    cd_offset = len(data)
    eocd = b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, len(centrals), len(centrals), len(cd), cd_offset, 0)
    copy = data + cd + eocd
    return {
        "repaired": True,
        "ok": bool(centrals),
        "entries": len(centrals),
        "copy": copy,
        "note": "Central directory rebuilt on an isolated copy. The source archive is not modified.",
    }
