"""Master Boot Record parser. Read-only; never writes a repaired table."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from usb_recovery.constants import (
    MBR_PARTITION_COUNT,
    MBR_PARTITION_ENTRY_SIZE,
    MBR_PARTITION_OFFSET,
    MBR_SIGNATURE,
)
from usb_recovery.models import PartitionInfo

# Common partition type IDs seen on USB pen drives.
PARTITION_TYPES = {
    0x00: "empty",
    0x01: "FAT12",
    0x04: "FAT16 <32MB",
    0x05: "extended",
    0x06: "FAT16",
    0x07: "NTFS/exFAT/HPFS",
    0x0B: "FAT32 CHS",
    0x0C: "FAT32 LBA",
    0x0E: "FAT16 LBA",
    0x0F: "extended LBA",
    0x11: "hidden FAT12",
    0x1B: "hidden FAT32",
    0x1C: "hidden FAT32 LBA",
    0x83: "Linux",
    0xEE: "GPT protective",
    0xEF: "EFI system",
}


@dataclass
class MbrEntry:
    status: int
    type_id: int
    start_lba: int
    sector_count: int
    bootable: bool
    chs_start: tuple[int, int, int]
    chs_end: tuple[int, int, int]


@dataclass
class MbrTable:
    boot_code_present: bool
    signature_valid: bool
    entries: list[MbrEntry]
    protective_gpt: bool
    raw: bytes


def _decode_chs(data: bytes) -> tuple[int, int, int]:
    head = data[0]
    sector = data[1] & 0x3F
    cyl = ((data[1] & 0xC0) << 2) | data[2]
    return (cyl, head, sector)


def parse_mbr(sector: bytes) -> MbrTable:
    if len(sector) < 512:
        sector = sector + bytes(512 - len(sector))
    signature_valid = sector[510:512] == MBR_SIGNATURE
    entries: list[MbrEntry] = []
    protective = False
    for i in range(MBR_PARTITION_COUNT):
        off = MBR_PARTITION_OFFSET + i * MBR_PARTITION_ENTRY_SIZE
        raw = sector[off : off + MBR_PARTITION_ENTRY_SIZE]
        status, type_id = raw[0], raw[4]
        start_lba, count = struct.unpack_from("<II", raw, 8)
        entry = MbrEntry(
            status=status,
            type_id=type_id,
            start_lba=start_lba,
            sector_count=count,
            bootable=bool(status & 0x80),
            chs_start=_decode_chs(raw[1:4]),
            chs_end=_decode_chs(raw[5:8]),
        )
        entries.append(entry)
        if type_id == 0xEE:
            protective = True
    boot_code_present = any(b != 0 for b in sector[0:440])
    return MbrTable(
        boot_code_present=boot_code_present,
        signature_valid=signature_valid,
        entries=entries,
        protective_gpt=protective,
        raw=sector[:512],
    )


def mbr_partitions(table: MbrTable) -> list[PartitionInfo]:
    parts: list[PartitionInfo] = []
    index = 0
    for entry in table.entries:
        if entry.type_id == 0x00 or entry.sector_count == 0:
            continue
        if entry.type_id == 0xEE:
            continue
        notes: list[str] = []
        if not table.signature_valid:
            notes.append("MBR signature 0x55AA missing or invalid")
        if entry.start_lba == 0 and entry.type_id != 0xEE:
            notes.append("Partition starts at LBA 0; may overlap the MBR")
        parts.append(
            PartitionInfo(
                index=index,
                start_lba=entry.start_lba,
                sector_count=entry.sector_count,
                scheme="mbr",
                type_id=f"0x{entry.type_id:02X}",
                type_name=PARTITION_TYPES.get(entry.type_id, "unknown"),
                bootable=entry.bootable,
                notes=notes,
            )
        )
        index += 1
    return parts


def find_extended_partitions(read_sector, table: MbrTable, max_depth: int = 16) -> list[PartitionInfo]:
    """Walk DOS extended partition chains. `read_sector(lba) -> 512 bytes`."""
    extras: list[PartitionInfo] = []
    index = 100
    for entry in table.entries:
        if entry.type_id not in (0x05, 0x0F):
            continue
        ebr_lba = entry.start_lba
        seen: set[int] = set()
        depth = 0
        while ebr_lba not in seen and depth < max_depth:
            seen.add(ebr_lba)
            depth += 1
            try:
                sector = read_sector(ebr_lba)
            except Exception:
                break
            ebr = parse_mbr(sector)
            logical = ebr.entries[0] if ebr.entries else None
            nxt = ebr.entries[1] if len(ebr.entries) > 1 else None
            if logical and logical.type_id not in (0x00, 0x05, 0x0F) and logical.sector_count:
                extras.append(
                    PartitionInfo(
                        index=index,
                        start_lba=ebr_lba + logical.start_lba,
                        sector_count=logical.sector_count,
                        scheme="mbr-extended",
                        type_id=f"0x{logical.type_id:02X}",
                        type_name=PARTITION_TYPES.get(logical.type_id, "unknown"),
                        notes=["logical partition via EBR chain"],
                    )
                )
                index += 1
            if not nxt or nxt.sector_count == 0 or nxt.type_id not in (0x05, 0x0F):
                break
            ebr_lba = entry.start_lba + nxt.start_lba
    return extras
