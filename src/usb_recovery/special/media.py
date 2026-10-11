"""Video codec stream and audio-frame analysis (337, 338)."""

from __future__ import annotations

import struct

NAL_TYPES = {
    1: "non-idr",
    5: "idr",
    6: "sei",
    7: "sps",
    8: "pps",
    9: "aud",
}


def analyze_codec_stream(data: bytes, *, limit: int = 2_000_000) -> dict:
    """Detect Annex-B H.264 NAL units even when the container is damaged."""
    window = data[:limit]
    nals = []
    start = 0
    while start < len(window) - 4:
        i = window.find(b"\x00\x00\x00\x01", start)
        if i < 0:
            i = window.find(b"\x00\x00\x01", start)
            prefix = 3
        else:
            prefix = 4
        if i < 0:
            break
        hdr = window[i + prefix] if i + prefix < len(window) else 0
        ntype = hdr & 0x1F
        nals.append({"offset": i, "type": NAL_TYPES.get(ntype, ntype)})
        start = i + prefix + 1
        if len(nals) >= 64:
            break
    mpeg = window.find(b"\x00\x00\x01\xb3")
    return {
        "nal_count": len(nals),
        "nals": nals[:32],
        "has_sps": any(n["type"] == "sps" for n in nals),
        "has_idr": any(n["type"] == "idr" for n in nals),
        "mpeg_seq": mpeg if mpeg >= 0 else None,
        "note": "NAL/start-code hits are a stream fragment, not a playable container.",
    }


def analyze_audio_frames(data: bytes, *, limit: int = 1_000_000) -> dict:
    """Identify MP3 / AAC-ADTS / WAV frames and estimate recoverable audio."""
    window = data[:limit]
    kind = None
    frames = 0
    if window.startswith(b"RIFF") and window[8:12] == b"WAVE":
        kind = "wav"
        has_fmt = b"fmt " in window[:256]
        has_data = b"data" in window[:1024]
        return {
            "kind": kind,
            "frames": 1 if has_data else 0,
            "fmt": has_fmt,
            "partial": not (has_fmt and has_data),
            "note": "WAV header parsed. Payload completeness is not guaranteed.",
        }
    if window.startswith(b"ID3") or (len(window) >= 2 and window[0] == 0xFF and (window[1] & 0xE0) == 0xE0):
        kind = "mp3"
        i = 0
        if window.startswith(b"ID3") and len(window) >= 10:
            i = 10 + (window[6] << 21 | window[7] << 14 | window[8] << 7 | window[9])
        while i + 4 <= len(window) and frames < 256:
            if window[i] == 0xFF and (window[i + 1] & 0xE0) == 0xE0:
                frames += 1
                # skip a conservative 32–1440 bytes; parse bitrate if possible
                br_index = (window[i + 2] >> 4) & 0x0F
                length = 144 if br_index else 96
                i += max(length, 4)
            else:
                i += 1
    if kind is None and len(window) >= 7 and window[0] == 0xFF and (window[1] & 0xF0) == 0xF0:
        kind = "aac-adts"
        i = 0
        while i + 7 <= len(window) and frames < 256:
            if window[i] == 0xFF and (window[i + 1] & 0xF0) == 0xF0:
                length = ((window[i + 3] & 0x03) << 11) | (window[i + 4] << 3) | ((window[i + 5] & 0xE0) >> 5)
                frames += 1
                i += max(length, 7)
            else:
                i += 1
    if kind is None and window.startswith(b"fLaC"):
        kind = "flac"
        frames = 1
    return {
        "kind": kind,
        "frames": frames,
        "partial": frames < 2 and kind not in {None, "wav", "flac"},
        "note": "Frame syncs estimate that some audio bytes exist; they do not rebuild a complete track.",
    }
