"""Identify a volume from its boot sector without mutating anything."""

from __future__ import annotations

import struct

from usb_recovery.constants import EXFAT_OEM, EXT_MAGIC, NTFS_OEM


def identify_boot_sector(sector: bytes) -> str | None:
    if len(sector) < 64:
        return None
    oem = sector[3:11]
    if oem == NTFS_OEM:
        return "ntfs"
    if oem == EXFAT_OEM:
        return "exfat"
    # FAT: BPB bytes-per-sector is 512/1024/2048/4096, and FS type string or cluster count.
    bps = struct.unpack_from("<H", sector, 0x0B)[0] if len(sector) >= 0x0D else 0
    if bps in (512, 1024, 2048, 4096):
        fat16_type = sector[0x36:0x3E] if len(sector) >= 0x3E else b""
        fat32_type = sector[0x52:0x5A] if len(sector) >= 0x5A else b""
        if fat32_type.startswith(b"FAT32"):
            return "fat32"
        if fat16_type.startswith(b"FAT16"):
            return "fat16"
        if fat16_type.startswith(b"FAT12"):
            return "fat12"
        # Infer from cluster count when the type string is blank (common on USB sticks).
        kind = _fat_kind_from_bpb(sector)
        if kind:
            return kind
    # ext2/3/4 superblock lives at offset 1024, not in the boot sector. Callers
    # that have a 2 KiB window can pass it; we also accept a superblock slice.
    if _looks_like_ext_super(sector):
        return "ext"
    if len(sector) >= 1024 + 0x40:
        if _looks_like_ext_super(sector[1024:1024 + 256]):
            return "ext"
    return None


def _fat_kind_from_bpb(sector: bytes) -> str | None:
    try:
        bps = struct.unpack_from("<H", sector, 0x0B)[0]
        spc = sector[0x0D]
        reserved = struct.unpack_from("<H", sector, 0x0E)[0]
        num_fats = sector[0x10]
        root_entries = struct.unpack_from("<H", sector, 0x11)[0]
        total16 = struct.unpack_from("<H", sector, 0x13)[0]
        fat16_sz = struct.unpack_from("<H", sector, 0x16)[0]
        total32 = struct.unpack_from("<I", sector, 0x20)[0] if len(sector) >= 0x24 else 0
        fat32_sz = struct.unpack_from("<I", sector, 0x24)[0] if len(sector) >= 0x28 else 0
    except struct.error:
        return None
    if bps == 0 or spc == 0 or num_fats == 0:
        return None
    total = total16 or total32
    fat_sz = fat16_sz or fat32_sz
    if total == 0 or fat_sz == 0:
        return None
    root_sectors = ((root_entries * 32) + (bps - 1)) // bps
    data_sectors = total - reserved - (num_fats * fat_sz) - root_sectors
    if data_sectors <= 0:
        return None
    clusters = data_sectors // spc
    if clusters < 4085:
        return "fat12"
    if clusters < 65525:
        return "fat16"
    return "fat32"


def _looks_like_ext_super(block: bytes) -> bool:
    if len(block) < 0x40:
        return False
    magic = struct.unpack_from("<H", block, 0x38)[0]
    return magic == EXT_MAGIC
