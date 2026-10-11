"""Embedded JPEG thumbnails in APP1/EXIF (277)."""

from __future__ import annotations

import struct


def extract_jpeg_thumbnail(data: bytes) -> bytes | None:
    """Return the first embedded JPEG after the primary SOI, if any."""
    if not data.startswith(b"\xff\xd8"):
        # some thumbs.db / caches store JPEG without wrapping
        idx = data.find(b"\xff\xd8\xff")
        if idx < 0:
            return None
        end = data.find(b"\xff\xd9", idx + 2)
        return data[idx : end + 2] if end > idx else data[idx : idx + 64_000]
    # skip primary SOI and look for another FFD8 inside EXIF
    i = 2
    while i + 4 < min(len(data), 128_000):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        if i + 4 > len(data):
            break
        length = struct.unpack_from(">H", data, i + 2)[0]
        payload = data[i + 4 : i + 2 + length]
        inner = payload.find(b"\xff\xd8\xff")
        if inner >= 0:
            blob = payload[inner:]
            eoi = blob.find(b"\xff\xd9")
            return blob[: eoi + 2] if eoi > 0 else blob
        i += 2 + length
        if marker == 0xDA:
            break
    return None
