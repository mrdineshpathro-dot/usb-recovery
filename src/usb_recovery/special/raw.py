"""Camera RAW fragment analyzer (339)."""

from __future__ import annotations

import struct

from usb_recovery.analysis.raw import classify_raw


def _ifd_tags(data: bytes, endian: str, offset: int, limit: int = 32) -> list[int]:
    if offset + 2 > len(data):
        return []
    count = struct.unpack_from(endian + "H", data, offset)[0]
    tags = []
    pos = offset + 2
    for _ in range(min(count, limit)):
        if pos + 12 > len(data):
            break
        tag = struct.unpack_from(endian + "H", data, pos)[0]
        tags.append(tag)
        pos += 12
    return tags


def analyze_raw_fragments(data: bytes) -> dict:
    kind = classify_raw(data)
    endian = "<" if data[:2] == b"II" else ">"
    ifd0 = struct.unpack_from(endian + "I", data, 4)[0] if len(data) >= 8 else 0
    tags = _ifd_tags(data, endian, ifd0) if ifd0 else []
    # 0x0111 StripOffsets, 0x0117 StripByteCounts, 0x014A SubIFD, 0x8769 Exif
    has_strips = 0x0111 in tags
    has_exif = 0x8769 in tags or 0x014A in tags
    return {
        "kind": kind,
        "ifd0": ifd0,
        "tag_count": len(tags),
        "has_strips": has_strips,
        "has_exif_or_subifd": has_exif,
        "note": (
            "TIFF/CR2/NEF/DNG markers identify a RAW candidate. "
            "Lost strips cannot be invented."
        ),
    }
