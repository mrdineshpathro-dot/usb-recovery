"""Alternate filesystem offsets and competing layout analysis (329, 330)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.identifier import identify_boot_sector
from usb_recovery.partitions.map import analyze_partitions


def scan_alternate_offsets(
    source: ReadOnlySource,
    *,
    stride: int = 512,
    limit: int = 128,
) -> list[dict]:
    """Check multiple offsets for valid filesystem boot structures (329)."""
    hits: list[dict] = []
    size = source.size
    steps = 0
    offset = 0
    while offset + 512 <= size and steps < limit:
        sector = source.read(offset, min(4096, size - offset))
        kind = identify_boot_sector(sector[:512] if len(sector) >= 512 else sector)
        if kind:
            hits.append({"offset": offset, "lba": offset // max(source.sector_size, 512), "filesystem": kind})
        offset += stride
        steps += 1
    return hits


def competing_layouts(source: ReadOnlySource) -> dict:
    """Compare partition-table vs super-floppy interpretations without writing (330)."""
    pmap = analyze_partitions(source)
    boots = scan_alternate_offsets(source, stride=max(source.sector_size, 512), limit=64)
    partition_starts = {p.start_offset for p in pmap.partitions}
    extras = [h for h in boots if h["offset"] not in partition_starts and not (h["offset"] == 0 and pmap.scheme in {"superfloppy", "none"})]
    lba0 = boots[0] if boots and boots[0]["offset"] == 0 else None
    conflict = bool(pmap.partitions) and lba0 is not None and pmap.scheme in {"mbr", "gpt"}
    return {
        "scheme": pmap.scheme,
        "partitions": [
            {"index": p.index, "start_lba": p.start_lba, "filesystem": p.filesystem, "type": p.type_name}
            for p in pmap.partitions
        ],
        "boot_hits": boots,
        "extra_boot_hits": extras,
        "competing": conflict or len(boots) > 1,
        "notes": list(pmap.notes),
        "note": "Layouts are compared read-only. Nothing is written back to the partition table.",
    }
