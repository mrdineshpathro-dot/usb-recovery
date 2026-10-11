"""GUID Partition Table parser. Compares backup GPT but never repairs it."""

from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass, field

from usb_recovery.constants import GPT_HEADER_LBA, GPT_SIGNATURE
from usb_recovery.models import PartitionInfo

# Microsoft basic data — typical USB / Windows data partition
BASIC_DATA_GUID = uuid.UUID("EBD0A0A2-B9E5-4433-87C0-68B6B72699C7")
EFI_SYSTEM_GUID = uuid.UUID("C12A7328-F81F-11D2-BA4B-00A0C93EC93B")
LINUX_FS_GUID = uuid.UUID("0FC63DAF-8483-4772-8E79-3D69D8477DE4")
LINUX_RAID_GUID = uuid.UUID("A19D880F-05FC-4D3B-A006-743F0F84911E")

TYPE_NAMES = {
    BASIC_DATA_GUID: "Microsoft basic data",
    EFI_SYSTEM_GUID: "EFI system",
    LINUX_FS_GUID: "Linux filesystem",
    uuid.UUID("00000000-0000-0000-0000-000000000000"): "unused",
}


def _guid_from_le(data: bytes) -> uuid.UUID:
    if len(data) < 16:
        return uuid.UUID(int=0)
    return uuid.UUID(bytes_le=data[:16])


@dataclass
class GptHeader:
    signature_valid: bool
    revision: int
    header_size: int
    current_lba: int
    backup_lba: int
    first_usable_lba: int
    last_usable_lba: int
    disk_guid: uuid.UUID
    partition_entry_lba: int
    num_entries: int
    entry_size: int
    crc32_header: int
    crc32_entries: int
    raw: bytes


@dataclass
class GptEntry:
    type_guid: uuid.UUID
    unique_guid: uuid.UUID
    first_lba: int
    last_lba: int
    attrs: int
    name: str


@dataclass
class GptTable:
    header: GptHeader
    entries: list[GptEntry]
    backup_header: GptHeader | None = None
    backup_mismatch: list[str] = field(default_factory=list)


def parse_gpt_header(sector: bytes, expected_lba: int | None = None) -> GptHeader:
    if len(sector) < 92:
        sector = sector + bytes(92 - len(sector))
    sig = sector[0:8]
    revision, header_size, crc = struct.unpack_from("<III", sector, 8)
    current_lba, backup_lba = struct.unpack_from("<QQ", sector, 24)
    first_usable, last_usable = struct.unpack_from("<QQ", sector, 40)
    disk_guid = _guid_from_le(sector[56:72])
    part_lba, num, ent_size, crc_entries = struct.unpack_from("<QIII", sector, 72)
    return GptHeader(
        signature_valid=sig == GPT_SIGNATURE,
        revision=revision,
        header_size=header_size,
        current_lba=current_lba,
        backup_lba=backup_lba,
        first_usable_lba=first_usable,
        last_usable_lba=last_usable,
        disk_guid=disk_guid,
        partition_entry_lba=part_lba,
        num_entries=num,
        entry_size=ent_size or 128,
        crc32_header=crc,
        crc32_entries=crc_entries,
        raw=sector,
    )


def parse_gpt_entries(blob: bytes, entry_size: int, count: int) -> list[GptEntry]:
    entries: list[GptEntry] = []
    size = entry_size or 128
    for i in range(count):
        off = i * size
        raw = blob[off : off + size]
        if len(raw) < 64:
            break
        type_guid = _guid_from_le(raw[0:16])
        if type_guid.int == 0:
            continue
        unique = _guid_from_le(raw[16:32])
        first, last, attrs = struct.unpack_from("<QQQ", raw, 32)
        name_raw = raw[56:128] if len(raw) >= 128 else raw[56:]
        name = name_raw.decode("utf-16le", errors="replace").split("\x00", 1)[0]
        entries.append(
            GptEntry(
                type_guid=type_guid,
                unique_guid=unique,
                first_lba=first,
                last_lba=last,
                attrs=attrs,
                name=name,
            )
        )
    return entries


def gpt_partitions(table: GptTable) -> list[PartitionInfo]:
    parts: list[PartitionInfo] = []
    for i, entry in enumerate(table.entries):
        count = int(entry.last_lba - entry.first_lba + 1)
        notes = list(table.backup_mismatch)
        if entry.last_lba < entry.first_lba:
            notes.append("last LBA precedes first LBA")
            count = 0
        parts.append(
            PartitionInfo(
                index=i,
                start_lba=int(entry.first_lba),
                sector_count=count,
                scheme="gpt",
                type_id=str(entry.type_guid),
                type_name=TYPE_NAMES.get(entry.type_guid, "unknown GUID"),
                label=entry.name or None,
                notes=notes,
            )
        )
    return parts


def compare_backup(primary: GptHeader, backup: GptHeader) -> list[str]:
    """Describe differences. Never copies one header over the other."""
    issues: list[str] = []
    if not backup.signature_valid:
        issues.append("Backup GPT signature is invalid; no repair was attempted")
        return issues
    if primary.disk_guid != backup.disk_guid:
        issues.append("Primary and backup GPT disk GUIDs differ")
    if primary.num_entries != backup.num_entries:
        issues.append("Primary and backup GPT partition counts differ")
    if primary.backup_lba != backup.current_lba:
        issues.append("Backup header is not at the LBA recorded by the primary header")
    return issues


def load_gpt(read_lba, sector_size: int = 512) -> GptTable | None:
    """`read_lba(lba) -> bytes` of one sector. Returns None if not GPT."""
    header_raw = read_lba(GPT_HEADER_LBA)
    header = parse_gpt_header(header_raw)
    if not header.signature_valid:
        return None
    table_bytes = header.num_entries * header.entry_size
    sectors = (table_bytes + sector_size - 1) // sector_size
    blob = b""
    for i in range(sectors):
        blob += read_lba(header.partition_entry_lba + i)
    entries = parse_gpt_entries(blob, header.entry_size, header.num_entries)
    backup = None
    mismatch: list[str] = []
    try:
        backup_raw = read_lba(header.backup_lba)
        backup = parse_gpt_header(backup_raw)
        mismatch = compare_backup(header, backup)
    except Exception:
        mismatch = ["Backup GPT header could not be read"]
    return GptTable(header=header, entries=entries, backup_header=backup, backup_mismatch=mismatch)
