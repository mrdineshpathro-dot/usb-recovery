"""Partition detection: MBR, GPT, and a super-floppy (no table) fallback."""

from __future__ import annotations

from dataclasses import dataclass, field

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.logging_config import get_logger
from usb_recovery.models import PartitionInfo
from usb_recovery.partitions.gpt import gpt_partitions, load_gpt, parse_gpt_header
from usb_recovery.partitions.mbr import find_extended_partitions, mbr_partitions, parse_mbr
from usb_recovery.constants import GPT_SIGNATURE, MBR_SIGNATURE

log = get_logger("partitions")


@dataclass
class PartitionMap:
    scheme: str
    partitions: list[PartitionInfo] = field(default_factory=list)
    mbr_valid: bool = False
    gpt_valid: bool = False
    protective_mbr: bool = False
    notes: list[str] = field(default_factory=list)
    overlapping: list[tuple[int, int]] = field(default_factory=list)


def detect_overlaps(parts: list[PartitionInfo]) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    ordered = sorted(parts, key=lambda p: p.start_lba)
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        a_end = a.start_lba + a.sector_count
        if a_end > b.start_lba:
            hits.append((a.index, b.index))
    return hits


def analyze_partitions(source: ReadOnlySource) -> PartitionMap:
    sector = source.read_sector(0)
    notes: list[str] = []
    mbr = parse_mbr(sector)
    gpt = None
    if mbr.protective_gpt or sector[512:520] == GPT_SIGNATURE:
        try:
            gpt = load_gpt(lambda lba: source.read_sector(lba), source.sector_size)
        except Exception as exc:
            notes.append(f"GPT header unreadable: {exc}")
            gpt = None
    else:
        # Some images place GPT at LBA 1 without a protective MBR type 0xEE.
        try:
            hdr = parse_gpt_header(source.read_sector(1))
            if hdr.signature_valid:
                gpt = load_gpt(lambda lba: source.read_sector(lba), source.sector_size)
        except Exception:
            gpt = None

    if gpt is not None and gpt.header.signature_valid:
        parts = gpt_partitions(gpt)
        overlaps = detect_overlaps(parts)
        if overlaps:
            notes.append(f"Overlapping GPT partitions: {overlaps}")
        notes.extend(gpt.backup_mismatch)
        return PartitionMap(
            scheme="gpt",
            partitions=parts,
            mbr_valid=mbr.signature_valid,
            gpt_valid=True,
            protective_mbr=mbr.protective_gpt,
            notes=notes,
            overlapping=overlaps,
        )

    if mbr.signature_valid:
        parts = mbr_partitions(mbr)
        try:
            parts.extend(
                find_extended_partitions(lambda lba: source.read_sector(lba), mbr)
            )
        except Exception as exc:
            notes.append(f"Extended partition walk failed: {exc}")
        # FAT/NTFS/exFAT boot sectors also end in 0x55AA. An "MBR" with no
        # partition entries is usually a super-floppy volume starting at LBA 0.
        if not parts:
            from usb_recovery.filesystems.identifier import identify_boot_sector

            kind = identify_boot_sector(sector)
            if kind:
                notes.append(
                    f"0x55AA present but no partition entries; treating LBA 0 as {kind} super-floppy"
                )
                total_lba = max(1, source.size // source.sector_size)
                return PartitionMap(
                    scheme="none",
                    partitions=[
                        PartitionInfo(
                            index=0,
                            start_lba=0,
                            sector_count=total_lba,
                            scheme="none",
                            type_id="superfloppy",
                            type_name=f"unpartitioned {kind}",
                            filesystem=kind,
                            notes=["assumed whole-device volume"],
                        )
                    ],
                    mbr_valid=True,
                    notes=notes,
                )
            notes.append("MBR present but no populated partition entries")
        overlaps = detect_overlaps(parts)
        if overlaps:
            notes.append(f"Overlapping MBR partitions: {overlaps}")
        return PartitionMap(
            scheme="mbr",
            partitions=parts,
            mbr_valid=True,
            gpt_valid=False,
            protective_mbr=False,
            notes=notes,
            overlapping=overlaps,
        )

    # Super-floppy: treat the whole device as one volume starting at LBA 0.
    total_lba = max(1, source.size // source.sector_size)
    notes.append(
        "No valid MBR or GPT signature. Treating the media as a super-floppy "
        "(filesystem may start at LBA 0). Common on some factory-formatted USB sticks."
    )
    return PartitionMap(
        scheme="none",
        partitions=[
            PartitionInfo(
                index=0,
                start_lba=0,
                sector_count=total_lba,
                scheme="none",
                type_id="superfloppy",
                type_name="unpartitioned volume",
                notes=["assumed whole-device volume"],
            )
        ],
        mbr_valid=sector[510:512] == MBR_SIGNATURE,
        notes=notes,
    )


def unallocated_ranges(
    source: ReadOnlySource, parts: list[PartitionInfo]
) -> list[tuple[int, int]]:
    """Return (start_lba, count) gaps not covered by partitions."""
    total = source.size // source.sector_size
    occupied = sorted(
        (p.start_lba, p.start_lba + p.sector_count) for p in parts if p.sector_count > 0
    )
    ranges: list[tuple[int, int]] = []
    cursor = 1  # skip MBR/GPT headers at LBA 0
    for start, end in occupied:
        if start > cursor:
            ranges.append((cursor, start - cursor))
        cursor = max(cursor, end)
    if cursor < total:
        ranges.append((cursor, total - cursor))
    return ranges


def search_lost_partitions(source: ReadOnlySource, step_sectors: int = 2048) -> list[PartitionInfo]:
    """Scan every `step_sectors` for FAT/NTFS/exFAT boot signatures.

    This never writes a reconstructed table back to the source.
    """
    from usb_recovery.filesystems.identifier import identify_boot_sector

    found: list[PartitionInfo] = []
    total = source.size // source.sector_size
    lba = 0
    index = 200
    while lba < total:
        try:
            sector = source.read_sector(lba)
        except Exception:
            lba += step_sectors
            continue
        kind = identify_boot_sector(sector)
        if kind:
            found.append(
                PartitionInfo(
                    index=index,
                    start_lba=lba,
                    sector_count=0,
                    scheme="heuristic",
                    type_id=kind,
                    type_name=f"possible {kind} boot sector",
                    filesystem=kind,
                    notes=[
                        f"Boot signature for {kind} found at LBA {lba}; "
                        "boundary is estimated, not repaired"
                    ],
                )
            )
            index += 1
        lba += step_sectors
    return found
