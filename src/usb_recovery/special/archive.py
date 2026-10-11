"""Archive member salvage for ZIP plus header detection for 7z/RAR (340)."""

from __future__ import annotations

from usb_recovery.reconstruct.archive import salvage_zip
from usb_recovery.special.zip import reconstruct_zip_directory

RAR4 = b"Rar!\x1a\x07\x00"
RAR5 = b"Rar!\x1a\x07\x01\x00"
SEVEN_Z = bytes.fromhex("377abcaf271c")


def salvage_archive_members(data: bytes) -> dict:
    """Extract structurally valid ZIP members; detect RAR/7z headers without unpacking."""
    if data.startswith(b"PK"):
        zip_info = salvage_zip(data)
        rebuilt = reconstruct_zip_directory(data)
        members = []
        for entry in zip_info.get("entries") or []:
            members.append(
                {
                    "name": entry.get("name"),
                    "offset": entry.get("offset"),
                    "truncated": bool(entry.get("truncated")),
                    "ok": not entry.get("truncated") and bool(entry.get("name")),
                }
            )
        return {
            "kind": "zip",
            "members": members,
            "count": sum(1 for m in members if m["ok"]),
            "repaired_eocd": rebuilt.get("repaired"),
            "note": "Valid local headers are listed. Truncated members are not silently extracted.",
        }
    if data.startswith(RAR5) or data.startswith(RAR4):
        return {
            "kind": "rar",
            "members": [],
            "count": 0,
            "note": "RAR signature detected. Full RAR unpacking is not implemented in this MVP.",
        }
    if data.startswith(SEVEN_Z):
        return {
            "kind": "7z",
            "members": [],
            "count": 0,
            "note": "7z signature detected. Packed streams are not decoded in this MVP.",
        }
    return {"kind": None, "members": [], "count": 0, "note": "No supported archive signature."}
