"""exFAT allocation-bitmap reconstruction (324)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.exfat import parse_exfat_boot


def reconstruct_exfat_bitmap(source: ReadOnlySource, volume_offset: int = 0) -> dict:
    """Read the first heap cluster as a surviving allocation bitmap (typical layout)."""
    boot = parse_exfat_boot(source.read(volume_offset, 512))
    if boot is None:
        return {"ok": False, "reason": "no exFAT boot sector"}
    # Cluster 2 is conventionally the allocation bitmap on simple volumes.
    data = source.read(volume_offset + boot.cluster_offset(2), min(boot.cluster_size, 1024 * 1024))
    allocated = 0
    free = 0
    bits_needed = boot.cluster_count
    inspected = min(bits_needed, len(data) * 8)
    for i in range(inspected):
        byte = data[i // 8]
        if byte & (1 << (i % 8)):
            allocated += 1
        else:
            free += 1
    return {
        "ok": True,
        "cluster_count": boot.cluster_count,
        "cluster_size": boot.cluster_size,
        "inspected_bits": inspected,
        "allocated": allocated,
        "free": free,
        "note": (
            "Bitmap bits are read, not rewritten. Cluster 2 is assumed to hold the bitmap "
            "on simple volumes; unusual layouts need a directory walk."
        ),
    }
