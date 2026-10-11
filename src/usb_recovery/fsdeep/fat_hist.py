"""FAT allocation-history analysis (321)."""

from __future__ import annotations

from usb_recovery.constants import FAT_DIR_ENTRY_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.fat import _fat_entry, _is_bad, _is_eoc, follow_chain, parse_fat_boot


def analyze_fat_history(source: ReadOnlySource, volume_offset: int = 0) -> dict:
    """Classify FAT clusters and compare them with directory starting clusters."""
    boot_sec = source.read(volume_offset, 512)
    boot = parse_fat_boot(boot_sec)
    if boot is None:
        return {"ok": False, "reason": "no FAT boot sector"}
    fat_bytes = boot.fat_size_sectors * boot.bytes_per_sector
    fat1 = source.read(volume_offset + boot.fat_offset, fat_bytes)
    fat2 = source.read(volume_offset + boot.fat_offset + fat_bytes, fat_bytes) if boot.num_fats > 1 else b""
    cluster_count = max(2, (boot.total_sectors * boot.bytes_per_sector - boot.data_offset) // boot.cluster_size)
    free = allocated = bad = eoc = 0
    chains: list[dict] = []
    for cluster in range(2, min(cluster_count + 2, 4096)):
        value = _fat_entry(fat1, boot.kind, cluster)
        if value == 0:
            free += 1
            continue
        if _is_bad(boot.kind, value):
            bad += 1
            continue
        if _is_eoc(boot.kind, value):
            eoc += 1
            allocated += 1
            continue
        allocated += 1
        chain = follow_chain(fat1, boot.kind, cluster, max_clusters=256)
        if len(chain) > 1:
            chains.append({"start": cluster, "length": len(chain), "contiguous": chain == list(range(chain[0], chain[0] + len(chain)))})
    root = source.read(volume_offset + boot.root_offset, boot.root_sectors * boot.bytes_per_sector or boot.cluster_size)
    dir_starts: list[dict] = []
    for i in range(0, len(root) - FAT_DIR_ENTRY_SIZE + 1, FAT_DIR_ENTRY_SIZE):
        entry = root[i : i + FAT_DIR_ENTRY_SIZE]
        if entry[0] in (0x00, 0x05) or entry[0x0B] == 0x0F:
            continue
        if entry[0] == 0xE5 or (entry[0x0B] & 0x18) == 0:
            cluster = int.from_bytes(entry[0x1A:0x1C], "little")
            if boot.kind == "fat32":
                cluster |= int.from_bytes(entry[0x14:0x16], "little") << 16
            size = int.from_bytes(entry[0x1C:0x20], "little")
            if cluster >= 2:
                fat_val = _fat_entry(fat1, boot.kind, cluster)
                dir_starts.append(
                    {
                        "name": bytes(entry[0:11]).decode("ascii", errors="replace"),
                        "deleted": entry[0] == 0xE5,
                        "cluster": cluster,
                        "size": size,
                        "fat_zeroed": fat_val == 0,
                    }
                )
    return {
        "ok": True,
        "kind": boot.kind,
        "cluster_size": boot.cluster_size,
        "free": free,
        "allocated": allocated,
        "bad": bad,
        "eoc": eoc,
        "fat_mirrors_match": bool(fat2) and fat1 == fat2,
        "chains": chains[:64],
        "directory": dir_starts[:128],
        "note": (
            "Deleted FAT names lose the first character. A zeroed FAT entry means the original "
            "cluster chain is gone; a contiguous heuristic is only a guess."
        ),
    }
