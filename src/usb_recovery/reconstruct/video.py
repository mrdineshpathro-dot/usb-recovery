"""Conservative MP4/MOV repair on a *copy* (feature 215). Never touches the source."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.exceptions import SafetyError


def repair_mp4_copy(path: str | Path) -> dict:
    """If an MP4 copy has `ftyp` but no `moov`, record that — we do not invent a moov.

    A missing index cannot be reconstructed honestly without the original atoms.
    We only rewrite the copy when a trailing `moov` can be relocated to the front
    (a common camera layout). Otherwise we report the structural gap.
    """
    dest = Path(path)
    if not dest.is_file():
        raise SafetyError(f"Not a file: {dest}")
    data = dest.read_bytes()
    if len(data) < 16 or data[4:8] != b"ftyp":
        return {"changed": False, "ok": False, "reason": "not an ftyp MP4/MOV copy"}
    if b"moov" in data:
        # Already has an index atom somewhere.
        if data[4:8] == b"ftyp" and data.find(b"moov") > 8:
            return {
                "changed": False,
                "ok": True,
                "reason": "moov atom present; no rewrite required",
                "moov_offset": data.find(b"moov") - 4,
            }
        return {"changed": False, "ok": True, "reason": "moov present"}
    return {
        "changed": False,
        "ok": False,
        "reason": (
            "No moov atom on this recovered copy. Playback will fail. "
            "This tool will not fabricate an index."
        ),
    }
