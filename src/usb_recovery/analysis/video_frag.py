"""Fragmented video structure checks (279)."""

from __future__ import annotations


def analyze_video_buffer(data: bytes) -> dict:
    has_ftyp = data[4:8] == b"ftyp" if len(data) >= 8 else False
    has_moov = b"moov" in data[: min(len(data), 2_000_000)]
    has_mdat = b"mdat" in data[: min(len(data), 2_000_000)]
    nal = data.find(b"\x00\x00\x00\x01")
    kind = "unknown"
    if has_ftyp:
        kind = "mp4"
    elif data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        kind = "avi"
    elif data[:4] == b"\x1aE\xdf\xa3":
        kind = "mkv"
    notes: list[str] = []
    if kind == "mp4" and has_mdat and not has_moov:
        notes.append("mdat without moov — frames may exist but the index is missing")
    if nal >= 0 and not has_ftyp:
        notes.append(f"Annex-B NAL start code at {nal}; possible H.264 fragment")
    playable = bool(has_ftyp and has_moov) or (kind == "avi" and b"movi" in data[:1_000_000])
    return {
        "kind": kind,
        "ftyp": has_ftyp,
        "moov": has_moov,
        "mdat": has_mdat,
        "nal_offset": nal if nal >= 0 else None,
        "likely_playable": playable,
        "notes": notes,
    }
