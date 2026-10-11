"""MP4 fragment and index analysis (332)."""

from __future__ import annotations

import struct


def _boxes(data: bytes, limit: int = 2_000_000) -> list[dict]:
    boxes = []
    offset = 0
    end = min(len(data), limit)
    while offset + 8 <= end:
        size = struct.unpack_from(">I", data, offset)[0]
        typ = data[offset + 4 : offset + 8]
        header = 8
        if size == 1 and offset + 16 <= end:
            size = struct.unpack_from(">Q", data, offset + 8)[0]
            header = 16
        if size == 0:
            size = len(data) - offset
        if size < header:
            break
        boxes.append({"type": typ.decode("latin1", errors="replace"), "offset": offset, "size": size})
        if typ in {b"moov", b"trak", b"mdia", b"minf", b"stbl"}:
            inner = _boxes(data[offset + header : offset + min(size, end - offset)], limit=size)
            for item in inner:
                item["offset"] += offset + header
            boxes.extend(inner)
        nxt = offset + size
        if nxt <= offset:
            break
        offset = nxt
        if len(boxes) > 512:
            break
    return boxes


def analyze_mp4_index(data: bytes) -> dict:
    boxes = _boxes(data)
    types = [b["type"] for b in boxes]
    stco = [b for b in boxes if b["type"] in {"stco", "co64"}]
    chunk_offsets: list[int] = []
    for box in stco[:2]:
        payload = data[box["offset"] + 12 : box["offset"] + box["size"]]
        if len(payload) < 8:
            continue
        count = struct.unpack_from(">I", payload, 4)[0]
        fmt = ">I" if box["type"] == "stco" else ">Q"
        width = 4 if box["type"] == "stco" else 8
        for i in range(min(count, 64)):
            pos = 8 + i * width
            if pos + width > len(payload):
                break
            chunk_offsets.append(struct.unpack_from(fmt, payload, pos)[0])
    has_ftyp = "ftyp" in types
    has_moov = "moov" in types
    has_mdat = "mdat" in types
    return {
        "boxes": types[:64],
        "ftyp": has_ftyp,
        "moov": has_moov,
        "mdat": has_mdat,
        "chunk_offsets": chunk_offsets,
        "playable": has_ftyp and has_moov and has_mdat,
        "note": (
            "mdat without moov is media data without an index. This tool will not fabricate moov."
            if has_mdat and not has_moov
            else "Index atoms listed from the buffer; the source is not modified."
        ),
    }
