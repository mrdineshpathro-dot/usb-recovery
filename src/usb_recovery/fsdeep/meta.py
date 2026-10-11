"""Directory cross-validation, metadata copies, and orphan correlation (325–327)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.fat import parse_fat_boot
from usb_recovery.filesystems.identifier import identify_boot_sector
from usb_recovery.filesystems.ntfs import parse_ntfs_boot
from usb_recovery.models import Candidate


def cross_validate_directory(candidates: list[Candidate]) -> list[dict]:
    """Compare directory size/path metadata against payload bytes (325)."""
    reports = []
    for item in candidates:
        content = item.extra.get("content")
        have = len(content) if isinstance(content, (bytes, bytearray)) else None
        issues: list[str] = []
        if have is not None and item.size and abs(have - item.size) > 16:
            issues.append(f"payload {have} bytes vs directory size {item.size}")
        if item.method == "metadata" and item.status == "carved":
            issues.append("method/status disagree")
        if item.original_path and item.original_path.endswith("/") and item.method != "metadata":
            issues.append("path looks like a directory but method is not metadata")
        if item.cluster_start is not None and item.cluster_start < 2:
            issues.append("implausible cluster start")
        reports.append(
            {
                "id": item.id,
                "name": item.name,
                "issues": issues,
                "ok": not issues,
                "payload_bytes": have,
            }
        )
    return reports


def compare_metadata_copies(source: ReadOnlySource, volume_offset: int = 0) -> dict:
    """Compare FAT mirrors or NTFS boot vs backup when present (326)."""
    sector = source.read(volume_offset, 512)
    kind = identify_boot_sector(sector)
    if kind and kind.startswith("fat"):
        boot = parse_fat_boot(sector)
        if boot is None:
            return {"ok": False, "kind": kind}
        fat_bytes = boot.fat_size_sectors * boot.bytes_per_sector
        fat1 = source.read(volume_offset + boot.fat_offset, fat_bytes)
        fat2 = (
            source.read(volume_offset + boot.fat_offset + fat_bytes, fat_bytes)
            if boot.num_fats > 1
            else b""
        )
        backup = None
        if boot.backup_boot_sector:
            backup_sec = source.read(volume_offset + boot.backup_boot_sector * boot.bytes_per_sector, 512)
            backup = backup_sec == sector
        return {
            "ok": True,
            "kind": boot.kind,
            "fat_mirrors_match": bool(fat2) and fat1 == fat2,
            "backup_boot_match": backup,
            "note": "Mismatched FAT mirrors are reported, never repaired.",
        }
    if kind == "ntfs":
        boot = parse_ntfs_boot(sector)
        if boot is None:
            return {"ok": False, "kind": "ntfs"}
        # NTFS backup boot is typically the last sector of the volume.
        last = source.size - boot.bytes_per_sector
        if last > 0:
            backup = source.read(last, boot.bytes_per_sector)
            return {
                "ok": True,
                "kind": "ntfs",
                "backup_boot_match": backup[:0x50] == sector[:0x50],
                "note": "Backup boot is compared, never copied over the primary.",
            }
    return {"ok": False, "kind": kind, "note": "No comparable metadata copies detected."}


def correlate_orphans(candidates: list[Candidate], cluster_size: int = 4096) -> list[dict]:
    """Relate orphaned entries to plausible parents by path/offset proximity (327)."""
    dirs = [c for c in candidates if c.file_type == "dir" or (c.original_path or "").endswith("/")]
    orphans = [c for c in candidates if c.method == "orphan" or not c.original_path]
    groups = []
    for item in orphans:
        nearby = []
        for folder in dirs:
            gap = abs(item.source_offset - folder.source_offset)
            if gap <= cluster_size * 8:
                nearby.append({"id": folder.id, "name": folder.name, "gap": gap})
        nearby.sort(key=lambda x: x["gap"])
        groups.append(
            {
                "id": item.id,
                "name": item.name,
                "candidates_parents": nearby[:5],
                "note": "Proximity is not proof of the original parent directory.",
            }
        )
    return groups
