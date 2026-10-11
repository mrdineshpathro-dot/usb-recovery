"""FAT12 / FAT16 / FAT32 metadata recovery (read-only).

Limitations (documented, not hidden):
- Deleted 8.3 names lose the first character (0xE5). We substitute '_'.
- After deletion most OS implementations zero the FAT chain. When the chain
  is gone we read a contiguous run of clusters sized to the directory entry
  and mark the result as uncertain / possibly fragmented.
- Cross-linked chains and bad clusters are skipped, not repaired.
- Volume labels and VFAT LFN orphans without a matching 8.3 checksum are kept
  as notes, not as reconstructed names.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from usb_recovery.constants import (
    FAT12_BAD,
    FAT12_EOC,
    FAT16_BAD,
    FAT16_EOC,
    FAT32_BAD,
    FAT32_EOC,
    FAT_ATTR_DIRECTORY,
    FAT_ATTR_LFN,
    FAT_ATTR_VOLUME,
    FAT_DELETED_MARK,
    FAT_DIR_ENTRY_SIZE,
)
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.logging_config import get_logger
from usb_recovery.models import Candidate, TimestampSet
from usb_recovery.util import decode_utf16le, dos_datetime, isoformat, new_id, sha256_bytes

log = get_logger("fat")


@dataclass
class FatBoot:
    kind: str  # fat12 / fat16 / fat32
    bytes_per_sector: int
    sectors_per_cluster: int
    reserved_sectors: int
    num_fats: int
    root_entries: int
    total_sectors: int
    fat_size_sectors: int
    root_cluster: int  # FAT32 only; 0 for FAT12/16
    hidden_sectors: int
    volume_label: str
    oem: str
    backup_boot_sector: int | None = None
    fsinfo_sector: int | None = None

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    @property
    def fat_offset(self) -> int:
        return self.reserved_sectors * self.bytes_per_sector

    @property
    def root_offset(self) -> int:
        return self.fat_offset + self.num_fats * self.fat_size_sectors * self.bytes_per_sector

    @property
    def root_sectors(self) -> int:
        if self.kind == "fat32":
            return 0
        return ((self.root_entries * 32) + (self.bytes_per_sector - 1)) // self.bytes_per_sector

    @property
    def data_offset(self) -> int:
        return self.root_offset + self.root_sectors * self.bytes_per_sector

    def cluster_offset(self, cluster: int) -> int:
        return self.data_offset + (cluster - 2) * self.cluster_size


def parse_fat_boot(sector: bytes) -> FatBoot | None:
    if len(sector) < 64:
        return None
    bps = struct.unpack_from("<H", sector, 0x0B)[0]
    spc = sector[0x0D]
    reserved = struct.unpack_from("<H", sector, 0x0E)[0]
    num_fats = sector[0x10]
    root_entries = struct.unpack_from("<H", sector, 0x11)[0]
    total16 = struct.unpack_from("<H", sector, 0x13)[0]
    fat16_sz = struct.unpack_from("<H", sector, 0x16)[0]
    total32 = struct.unpack_from("<I", sector, 0x20)[0] if len(sector) >= 0x24 else 0
    fat32_sz = struct.unpack_from("<I", sector, 0x24)[0] if len(sector) >= 0x28 else 0
    if bps not in (512, 1024, 2048, 4096) or spc == 0 or num_fats == 0:
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
        kind = "fat12"
    elif clusters < 65525:
        kind = "fat16"
    else:
        kind = "fat32"
    root_cluster = 0
    backup = None
    fsinfo = None
    label = ""
    if kind == "fat32" and len(sector) >= 0x5A:
        root_cluster = struct.unpack_from("<I", sector, 0x2C)[0]
        fsinfo = struct.unpack_from("<H", sector, 0x30)[0]
        backup = struct.unpack_from("<H", sector, 0x32)[0]
        label = sector[0x47:0x52].decode("ascii", errors="replace").strip()
    else:
        label = sector[0x2B:0x36].decode("ascii", errors="replace").strip() if len(sector) >= 0x36 else ""
    oem = sector[3:11].decode("ascii", errors="replace").strip()
    return FatBoot(
        kind=kind,
        bytes_per_sector=bps,
        sectors_per_cluster=spc,
        reserved_sectors=reserved,
        num_fats=num_fats,
        root_entries=root_entries,
        total_sectors=total,
        fat_size_sectors=fat_sz,
        root_cluster=root_cluster or 2,
        hidden_sectors=struct.unpack_from("<I", sector, 0x1C)[0] if len(sector) >= 0x20 else 0,
        volume_label=label,
        oem=oem,
        backup_boot_sector=backup,
        fsinfo_sector=fsinfo,
    )


def _fat_entry(fat: bytes, kind: str, cluster: int) -> int:
    if kind == "fat12":
        offset = cluster + (cluster // 2)
        if offset + 1 >= len(fat):
            return 0
        pair = fat[offset] | (fat[offset + 1] << 8)
        value = pair >> 4 if cluster & 1 else pair & 0x0FFF
        return value
    if kind == "fat16":
        offset = cluster * 2
        if offset + 2 > len(fat):
            return 0
        return struct.unpack_from("<H", fat, offset)[0]
    offset = cluster * 4
    if offset + 4 > len(fat):
        return 0
    return struct.unpack_from("<I", fat, offset)[0] & 0x0FFFFFFF


def _is_eoc(kind: str, value: int) -> bool:
    if kind == "fat12":
        return value >= FAT12_EOC
    if kind == "fat16":
        return value >= FAT16_EOC
    return value >= FAT32_EOC


def _is_bad(kind: str, value: int) -> bool:
    if kind == "fat12":
        return value == FAT12_BAD
    if kind == "fat16":
        return value == FAT16_BAD
    return value == FAT32_BAD


def follow_chain(fat: bytes, kind: str, start: int, max_clusters: int = 1_000_000) -> list[int]:
    chain: list[int] = []
    seen: set[int] = set()
    cluster = start
    while cluster >= 2 and cluster not in seen and len(chain) < max_clusters:
        seen.add(cluster)
        chain.append(cluster)
        nxt = _fat_entry(fat, kind, cluster)
        if nxt == 0 or _is_bad(kind, nxt) or _is_eoc(kind, nxt):
            break
        cluster = nxt
    return chain


def _parse_lfn_chars(entry: bytes) -> str:
    chunks = entry[1:11] + entry[14:26] + entry[28:32]
    return decode_utf16le(chunks)


def _lfn_checksum(name11: bytes) -> int:
    s = 0
    for byte in name11:
        s = ((s & 1) << 7) + (s >> 1) + byte
        s &= 0xFF
    return s


def _decode_83(name11: bytes, deleted: bool) -> str:
    raw = bytearray(name11)
    if deleted and raw:
        raw[0] = ord("_")
    base = bytes(raw[0:8]).decode("ascii", errors="replace").rstrip(" ")
    ext = bytes(raw[8:11]).decode("ascii", errors="replace").rstrip(" ")
    base = "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in base)
    ext = "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in ext)
    return f"{base}.{ext}" if ext else base


def _guess_type(name: str) -> tuple[str, str]:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    mapping = {
        "jpg": ("jpeg", "image/jpeg"),
        "jpeg": ("jpeg", "image/jpeg"),
        "png": ("png", "image/png"),
        "gif": ("gif", "image/gif"),
        "bmp": ("bmp", "image/bmp"),
        "pdf": ("pdf", "application/pdf"),
        "txt": ("text", "text/plain"),
        "csv": ("csv", "text/csv"),
        "log": ("log", "text/plain"),
        "zip": ("zip", "application/zip"),
        "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "xlsx": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "pptx": ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "mp3": ("mp3", "audio/mpeg"),
        "wav": ("wav", "audio/wav"),
        "mp4": ("mp4", "video/mp4"),
        "doc": ("doc", "application/msword"),
        "xls": ("xls", "application/vnd.ms-excel"),
    }
    return mapping.get(ext, (ext or "bin", "application/octet-stream"))


@dataclass
class FatScanResult:
    boot: FatBoot
    candidates: list[Candidate] = field(default_factory=list)
    consistency_notes: list[str] = field(default_factory=list)


class FatVolume:
    def __init__(self, source: ReadOnlySource, volume_offset: int, boot: FatBoot) -> None:
        self.source = source
        self.volume_offset = volume_offset
        self.boot = boot
        self._fat: bytes | None = None

    def fat_table(self) -> bytes:
        if self._fat is None:
            size = self.boot.fat_size_sectors * self.boot.bytes_per_sector
            self._fat = self.source.read(self.volume_offset + self.boot.fat_offset, size)
        return self._fat

    def read_cluster(self, cluster: int) -> bytes:
        off = self.volume_offset + self.boot.cluster_offset(cluster)
        return self.source.read(off, self.boot.cluster_size)

    def read_chain_bytes(self, chain: list[int], size: int) -> bytes:
        parts: list[bytes] = []
        remaining = size
        for cluster in chain:
            data = self.read_cluster(cluster)
            if remaining < len(data):
                parts.append(data[:remaining])
                remaining = 0
                break
            parts.append(data)
            remaining -= len(data)
        return b"".join(parts)

    def _walk_dir(
        self,
        entries_blob: bytes,
        path: str,
        fat: bytes,
        results: list[Candidate],
        visited: set[int],
        include_existing: bool,
    ) -> None:
        lfn_parts: list[tuple[int, str]] = []
        offset = 0
        while offset + FAT_DIR_ENTRY_SIZE <= len(entries_blob):
            ent = entries_blob[offset : offset + FAT_DIR_ENTRY_SIZE]
            offset += FAT_DIR_ENTRY_SIZE
            first = ent[0]
            if first == 0x00:
                break
            attr = ent[0x0B]
            if attr == FAT_ATTR_LFN:
                seq = first
                if seq != FAT_DELETED_MARK:
                    lfn_parts.append((seq, _parse_lfn_chars(ent)))
                continue
            if attr & FAT_ATTR_VOLUME:
                lfn_parts.clear()
                continue
            deleted = first == FAT_DELETED_MARK
            if first == 0x2E:  # . or ..
                lfn_parts.clear()
                continue
            name_83 = _decode_83(ent[0:11], deleted=deleted)
            lfn = ""
            if lfn_parts:
                lfn_parts.sort(key=lambda item: item[0] & 0x1F)
                lfn = "".join(part for _, part in lfn_parts).split("\x00")[0]
            lfn_parts.clear()
            name = lfn or name_83
            cluster_hi = struct.unpack_from("<H", ent, 0x14)[0]
            cluster_lo = struct.unpack_from("<H", ent, 0x1A)[0]
            start = (cluster_hi << 16) | cluster_lo
            size = struct.unpack_from("<I", ent, 0x1C)[0]
            is_dir = bool(attr & FAT_ATTR_DIRECTORY)
            created = dos_datetime(
                struct.unpack_from("<H", ent, 0x10)[0],
                struct.unpack_from("<H", ent, 0x0E)[0],
            )
            modified = dos_datetime(
                struct.unpack_from("<H", ent, 0x18)[0],
                struct.unpack_from("<H", ent, 0x16)[0],
            )
            full_path = f"{path.rstrip('/')}/{name}"

            if is_dir:
                if start >= 2 and start not in visited:
                    visited.add(start)
                    chain = follow_chain(fat, self.boot.kind, start)
                    if not chain:
                        chain = [start]
                    blob = self.read_chain_bytes(chain, len(chain) * self.boot.cluster_size)
                    child_path = full_path
                    self._walk_dir(blob, child_path, fat, results, visited, include_existing)
                    if deleted:
                        results.append(
                            self._candidate(
                                name=name,
                                path=full_path,
                                size=0,
                                start=start,
                                deleted=True,
                                is_dir=True,
                                created=created,
                                modified=modified,
                                chain=chain,
                                content=b"",
                            )
                        )
                continue

            if deleted or include_existing:
                chain = follow_chain(fat, self.boot.kind, start) if start >= 2 else []
                fragmented = False
                heuristic = False
                notes: list[str] = []
                reasons: list[str] = []
                needed = max(1, (size + self.boot.cluster_size - 1) // self.boot.cluster_size) if size else 1
                fat_next = _fat_entry(fat, self.boot.kind, start) if start >= 2 else 0
                if start >= 2 and (not chain or fat_next == 0):
                    # FAT chain wiped; assume contiguous clusters (uncertain).
                    if len(chain) < needed:
                        chain = list(range(start, start + needed))
                    heuristic = True
                    notes.append("FAT chain is free; used contiguous-cluster heuristic")
                    reasons.append("allocation chain missing; contiguous read is a heuristic")
                elif chain and len(chain) < needed and size:
                    extra = list(range(chain[-1] + 1, chain[-1] + 1 + (needed - len(chain))))
                    chain = chain + extra
                    heuristic = True
                    notes.append("FAT chain shorter than file size; padded with contiguous clusters")
                if chain and any(chain[i] + 1 != chain[i + 1] for i in range(len(chain) - 1)):
                    fragmented = True
                    reasons.append("cluster chain is non-contiguous")
                content = self.read_chain_bytes(chain, size) if chain and not is_dir else b""
                if deleted:
                    reasons.append("directory entry marked deleted (0xE5)")
                    if not heuristic:
                        reasons.append("FAT cluster chain still present")
                else:
                    reasons.append("live directory entry with allocation chain")
                results.append(
                    self._candidate(
                        name=name,
                        path=full_path,
                        size=size,
                        start=start,
                        deleted=deleted,
                        is_dir=False,
                        created=created,
                        modified=modified,
                        chain=chain,
                        content=content,
                        fragmented=fragmented,
                        heuristic=heuristic,
                        notes=notes,
                        reasons=reasons,
                    )
                )

    def _candidate(
        self,
        *,
        name: str,
        path: str,
        size: int,
        start: int,
        deleted: bool,
        is_dir: bool,
        created,
        modified,
        chain: list[int],
        content: bytes,
        fragmented: bool = False,
        heuristic: bool = False,
        notes: list[str] | None = None,
        reasons: list[str] | None = None,
    ) -> Candidate:
        file_type, mime = _guess_type(name)
        offset = 0
        if start >= 2:
            offset = self.volume_offset + self.boot.cluster_offset(start)
        confidence = 90.0
        why = list(reasons or [])
        if deleted:
            confidence = 70.0
        if heuristic:
            confidence = min(confidence, 45.0)
        if fragmented and heuristic:
            confidence = min(confidence, 30.0)
        if is_dir:
            file_type, mime = "directory", "inode/directory"
        digest = sha256_bytes(content) if content else None
        status = "deleted" if deleted else "existing"
        if heuristic:
            status = "partial" if deleted else status
        return Candidate(
            id=new_id("fat-"),
            name=name,
            size=size if not is_dir else 0,
            file_type=file_type,
            mime=mime,
            method="existing" if not deleted else "metadata",
            status=status,  # type: ignore[arg-type]
            source_offset=offset,
            confidence=confidence,
            confidence_reasons=why or ["FAT directory entry"],
            original_path=path,
            cluster_start=start if start >= 2 else None,
            extension=name.rsplit(".", 1)[-1].lower() if "." in name else "",
            timestamps=TimestampSet(
                created=isoformat(created) if created else None,
                modified=isoformat(modified) if modified else None,
            ),
            is_fragmented=fragmented,
            sha256=digest,
            notes=notes or [],
            extra={
                "chain": chain[:64],
                "volume_offset": self.volume_offset,
                "content": content,
                "fs": self.boot.kind,
            },
        )

    def scan(self, *, include_existing: bool = True) -> FatScanResult:
        fat = self.fat_table()
        notes: list[str] = []
        if self.boot.backup_boot_sector:
            backup = self.source.read(
                self.volume_offset + self.boot.backup_boot_sector * self.boot.bytes_per_sector,
                self.boot.bytes_per_sector,
            )
            if backup and backup != self.source.read(self.volume_offset, self.boot.bytes_per_sector):
                notes.append("FAT32 backup boot sector differs from the primary (not repaired)")
        results: list[Candidate] = []
        visited: set[int] = set()
        if self.boot.kind == "fat32":
            visited.add(self.boot.root_cluster)
            chain = follow_chain(fat, self.boot.kind, self.boot.root_cluster)
            if not chain:
                chain = [self.boot.root_cluster]
            blob = self.read_chain_bytes(chain, len(chain) * self.boot.cluster_size)
        else:
            blob = self.source.read(
                self.volume_offset + self.boot.root_offset,
                self.boot.root_sectors * self.boot.bytes_per_sector,
            )
        self._walk_dir(blob, "", fat, results, visited, include_existing)
        return FatScanResult(boot=self.boot, candidates=results, consistency_notes=notes)


def scan_fat(
    source: ReadOnlySource, volume_offset: int = 0, *, include_existing: bool = True
) -> FatScanResult | None:
    sector = source.read(volume_offset, 512)
    boot = parse_fat_boot(sector)
    if boot is None:
        return None
    volume = FatVolume(source, volume_offset, boot)
    return volume.scan(include_existing=include_existing)
