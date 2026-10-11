"""Sector alignment analyzer (271)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.identifier import identify_boot_sector
from usb_recovery.partitions.map import analyze_partitions


def analyze_alignment(source: ReadOnlySource) -> dict:
    notes: list[str] = []
    pmap = analyze_partitions(source)
    sector = source.sector_size or 512
    for part in pmap.partitions:
        offset = part.start_lba * 512
        if part.start_lba and (part.start_lba * 512) % 4096:
            notes.append(
                f"Partition {part.index} starts at LBA {part.start_lba} "
                f"({offset} bytes) which is not 4 KiB aligned"
            )
        boot = source.read(offset, 512)
        kind = identify_boot_sector(boot)
        bps = int.from_bytes(boot[0x0B:0x0D], "little") if len(boot) >= 0x0D else 0
        if bps and bps != sector and bps in (512, 1024, 2048, 4096):
            notes.append(
                f"Partition {part.index} BPB bytes/sector={bps} but source sector_size={sector}"
            )
        if kind:
            part.filesystem = kind
    if source.size % 512:
        notes.append("Image size is not a multiple of 512 bytes")
    return {
        "scheme": pmap.scheme,
        "sector_size": sector,
        "partitions": [
            {"index": p.index, "lba": p.start_lba, "fs": p.filesystem} for p in pmap.partitions
        ],
        "issues": notes,
        "aligned_4k": not any("not 4 KiB" in n for n in notes),
    }
