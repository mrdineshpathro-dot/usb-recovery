"""Camera RAW signatures (278) — CR2/NEF/ARW/DNG/RW2 via TIFF + magic."""

from __future__ import annotations

RAW_SIGNATURES = [
    {
        "id": "cr2",
        "name": "Canon CR2",
        "header": b"II*\x00",
        "extra": b"CR\x02\x00",
        "extra_offset": 8,
        "extensions": ["cr2"],
    },
    {
        "id": "dng",
        "name": "Adobe DNG",
        "header": b"II*\x00",
        "extra": b"DNG",
        "extensions": ["dng"],
    },
    {
        "id": "arw",
        "name": "Sony ARW",
        "header": b"II*\x00",
        "extensions": ["arw"],
    },
    {
        "id": "nef",
        "name": "Nikon NEF",
        "header": b"MM\x00*",
        "extensions": ["nef"],
    },
    {
        "id": "rw2",
        "name": "Panasonic RW2",
        "header": b"IIU\x00",
        "extensions": ["rw2"],
    },
]


def classify_raw(data: bytes) -> str | None:
    if data.startswith(b"II*\x00") and data[8:12] == b"CR\x02\x00":
        return "cr2"
    if data.startswith(b"IIU\x00"):
        return "rw2"
    if b"DNG" in data[:256] and data[:4] in {b"II*\x00", b"MM\x00*"}:
        return "dng"
    if data.startswith(b"MM\x00*"):
        return "nef"
    if data.startswith(b"II*\x00"):
        return "tiff-raw"
    return None
