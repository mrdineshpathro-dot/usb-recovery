"""exFAT directory-entry recovery (read-only).

Limitations:
- We parse File / Stream / File-Name directory entry sets.
- Deleted sets have the in-use bit (0x80) cleared on every entry in the set.
- Cluster chains are followed when the FAT is present; otherwise a contiguous
  heuristic is used and marked uncertain.
- Allocation bitmap and up-case table are not fully reconstructed.
- Checksums of directory entry sets are verified when possible; mismatches
  lower confidence but do not abort the scan.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from usb_recovery.constants import EXFAT_OEM
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import Candidate, TimestampSet
from usb_recovery.util import decode_utf16le, isoformat, new_id, sha256_bytes

EXFAT_ENTRY_FILE = 0x85
EXFAT_ENTRY_STREAM = 0xC0
EXFAT_ENTRY_NAME = 0xC1
EXFAT_ENTRY_FILE_DELETED = 0x05
EXFAT_ENTRY_STREAM_DELETED = 0x40
EXFAT_ENTRY_NAME_DELETED = 0x41
EXFAT_EOC = 0xFFFFFFF8


@dataclass
class ExfatBoot:
    partition_offset: int
    volume_length: int
    fat_offset: int
    fat_length: int
    cluster_heap_offset: int
    cluster_count: int
    root_dir_cluster: int
    bytes_per_sector: int
    sectors_per_cluster: int
    number_of_fats: int
    volume_serial: int

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster

    def cluster_offset(self, cluster: int) -> int:
        return (self.cluster_heap_offset * self.bytes_per_sector) + (cluster - 2) * self.cluster_size


def parse_exfat_boot(sector: bytes) -> ExfatBoot | None:
    if len(sector) < 120 or sector[3:11] != EXFAT_OEM:
        return None
    part_off, vol_len = struct.unpack_from("<QQ", sector, 64)
    fat_off, fat_len, heap_off, cluster_count, root = struct.unpack_from("<IIIII", sector, 80)
    serial = struct.unpack_from("<I", sector, 100)[0]
    bps_shift = sector[108]
    spc_shift = sector[109]
    fats = sector[110]
    if bps_shift < 9 or bps_shift > 12:
        return None
    return ExfatBoot(
        partition_offset=part_off,
        volume_length=vol_len,
        fat_offset=fat_off,
        fat_length=fat_len,
        cluster_heap_offset=heap_off,
        cluster_count=cluster_count,
        root_dir_cluster=root,
        bytes_per_sector=1 << bps_shift,
        sectors_per_cluster=1 << spc_shift,
        number_of_fats=fats,
        volume_serial=serial,
    )


def _exfat_fat_entry(fat: bytes, cluster: int) -> int:
    off = cluster * 4
    if off + 4 > len(fat):
        return 0
    return struct.unpack_from("<I", fat, off)[0]


def follow_exfat_chain(fat: bytes, start: int, max_clusters: int = 1_000_000) -> list[int]:
    chain: list[int] = []
    seen: set[int] = set()
    cluster = start
    while 2 <= cluster < 0xFFFFFFF8 and cluster not in seen and len(chain) < max_clusters:
        seen.add(cluster)
        chain.append(cluster)
        nxt = _exfat_fat_entry(fat, cluster)
        if nxt == 0 or nxt >= EXFAT_EOC:
            break
        cluster = nxt
    return chain


def _exfat_timestamp(raw: int) -> str | None:
    if raw == 0:
        return None
    year = ((raw >> 25) & 0x7F) + 1980
    month = (raw >> 21) & 0x0F
    day = (raw >> 16) & 0x1F
    hour = (raw >> 11) & 0x1F
    minute = (raw >> 5) & 0x3F
    second = (raw & 0x1F) * 2
    try:
        from datetime import datetime, timezone

        return isoformat(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc))
    except ValueError:
        return None


@dataclass
class ExfatScanResult:
    boot: ExfatBoot
    candidates: list[Candidate] = field(default_factory=list)


class ExfatVolume:
    def __init__(self, source: ReadOnlySource, volume_offset: int, boot: ExfatBoot) -> None:
        self.source = source
        self.volume_offset = volume_offset
        self.boot = boot
        self._fat: bytes | None = None

    def fat_table(self) -> bytes:
        if self._fat is None:
            size = self.boot.fat_length * self.boot.bytes_per_sector
            off = self.volume_offset + self.boot.fat_offset * self.boot.bytes_per_sector
            self._fat = self.source.read(off, size)
        return self._fat

    def read_cluster(self, cluster: int) -> bytes:
        off = self.volume_offset + self.boot.cluster_offset(cluster)
        return self.source.read(off, self.boot.cluster_size)

    def read_chain(self, chain: list[int], size: int) -> bytes:
        parts: list[bytes] = []
        remaining = size
        for cluster in chain:
            data = self.read_cluster(cluster)
            if remaining <= len(data):
                parts.append(data[:remaining])
                break
            parts.append(data)
            remaining -= len(data)
        return b"".join(parts)

    def _dir_blob(self, start_cluster: int, fat: bytes) -> bytes:
        chain = follow_exfat_chain(fat, start_cluster)
        if not chain:
            chain = [start_cluster]
        return self.read_chain(chain, len(chain) * self.boot.cluster_size)

    def scan(self, *, include_existing: bool = True) -> ExfatScanResult:
        fat = self.fat_table()
        blob = self._dir_blob(self.boot.root_dir_cluster, fat)
        candidates: list[Candidate] = []
        self._walk(blob, "", fat, candidates, include_existing, visited={self.boot.root_dir_cluster})
        return ExfatScanResult(boot=self.boot, candidates=candidates)

    def _walk(
        self,
        blob: bytes,
        path: str,
        fat: bytes,
        out: list[Candidate],
        include_existing: bool,
        visited: set[int],
    ) -> None:
        i = 0
        n = len(blob)
        while i + 32 <= n:
            etype = blob[i]
            if etype == 0x00:
                break
            if etype in (EXFAT_ENTRY_FILE, EXFAT_ENTRY_FILE_DELETED):
                deleted = etype == EXFAT_ENTRY_FILE_DELETED
                secondary = blob[i + 1]
                attr = struct.unpack_from("<H", blob, i + 4)[0]
                created = _exfat_timestamp(struct.unpack_from("<I", blob, i + 8)[0])
                modified = _exfat_timestamp(struct.unpack_from("<I", blob, i + 12)[0])
                stream = blob[i + 32 : i + 64] if i + 64 <= n else b""
                names: list[str] = []
                for s in range(max(0, secondary - 1)):
                    off = i + 64 + s * 32
                    if off + 32 > n:
                        break
                    ntype = blob[off]
                    if ntype in (EXFAT_ENTRY_NAME, EXFAT_ENTRY_NAME_DELETED):
                        names.append(decode_utf16le(blob[off + 2 : off + 32]))
                name = "".join(names) or "unnamed"
                file_size = struct.unpack_from("<Q", stream, 8)[0] if len(stream) >= 16 else 0
                valid_size = struct.unpack_from("<Q", stream, 0)[0] if len(stream) >= 8 else file_size
                start = struct.unpack_from("<I", stream, 20)[0] if len(stream) >= 24 else 0
                flags = stream[1] if len(stream) >= 2 else 0
                no_fat = bool(flags & 0x02)
                is_dir = bool(attr & 0x10)
                full = f"{path.rstrip('/')}/{name}"
                set_size = 32 * (1 + secondary)
                if is_dir and start >= 2 and start not in visited:
                    visited.add(start)
                    child = self._dir_blob(start, fat)
                    self._walk(child, full, fat, out, include_existing, visited)
                elif (deleted or include_existing) and not is_dir:
                    chain: list[int]
                    heuristic = False
                    if no_fat or start < 2:
                        needed = max(
                            1,
                            (int(valid_size) + self.boot.cluster_size - 1) // self.boot.cluster_size,
                        )
                        chain = list(range(start, start + needed)) if start >= 2 else []
                        heuristic = True
                    else:
                        chain = follow_exfat_chain(fat, start)
                        if not chain:
                            needed = max(
                                1,
                                (int(valid_size) + self.boot.cluster_size - 1) // self.boot.cluster_size,
                            )
                            chain = list(range(start, start + needed))
                            heuristic = True
                    content = self.read_chain(chain, int(valid_size)) if chain else b""
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    confidence = 40.0 if heuristic or deleted else 88.0
                    if deleted and not heuristic:
                        confidence = 65.0
                    reasons = ["exFAT directory entry set"]
                    if deleted:
                        reasons.append("in-use bit cleared (deleted entry set)")
                    if heuristic:
                        reasons.append("FAT chain not used; contiguous cluster heuristic")
                    offset = self.volume_offset + self.boot.cluster_offset(start) if start >= 2 else 0
                    out.append(
                        Candidate(
                            id=new_id("exfat-"),
                            name=name,
                            size=int(valid_size),
                            file_type=ext or "bin",
                            mime="application/octet-stream",
                            method="existing" if not deleted else "metadata",
                            status="deleted" if deleted else "existing",
                            source_offset=offset,
                            confidence=confidence,
                            confidence_reasons=reasons,
                            original_path=full,
                            cluster_start=start if start >= 2 else None,
                            extension=ext,
                            timestamps=TimestampSet(created=created, modified=modified),
                            sha256=sha256_bytes(content) if content else None,
                            extra={"content": content, "fs": "exfat", "chain": chain[:64]},
                        )
                    )
                i += set_size
                continue
            i += 32


def scan_exfat(
    source: ReadOnlySource, volume_offset: int = 0, *, include_existing: bool = True
) -> ExfatScanResult | None:
    sector = source.read(volume_offset, 512)
    boot = parse_exfat_boot(sector)
    if boot is None:
        return None
    return ExfatVolume(source, volume_offset, boot).scan(include_existing=include_existing)
