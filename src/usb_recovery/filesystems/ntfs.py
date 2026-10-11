"""Read-only NTFS $MFT analysis.

Implemented:
- Boot sector (OEM NTFS, MFT cluster, record size)
- FILE record walk for in-use and deleted records
- STANDARD_INFORMATION timestamps, FILE_NAME, resident/non-resident DATA
- Runlist reconstruction for non-resident unnamed $DATA
- Alternate data stream names (non-empty attribute names on $DATA)

Not implemented (documented):
- $LogFile / USN journal replay
- Attribute lists spanning multiple records (we skip and note)
- Compression, encryption, sparse runs beyond a basic skip
- Directory index ($I30) reconstruction of orphaned names
- Repair of the MFT itself
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from usb_recovery.constants import (
    NTFS_ATTR_DATA,
    NTFS_ATTR_END,
    NTFS_ATTR_FILE_NAME,
    NTFS_ATTR_STANDARD_INFORMATION,
    NTFS_FILE_DIRECTORY,
    NTFS_FILE_IN_USE,
    NTFS_FILE_RECORD_MAGIC,
    NTFS_OEM,
)
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import Candidate, TimestampSet
from usb_recovery.util import decode_utf16le, isoformat, new_id, sha256_bytes

WINDOWS_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def filetime_to_iso(raw: int) -> str | None:
    if raw == 0:
        return None
    try:
        ts = WINDOWS_EPOCH + timedelta(microseconds=raw / 10)
        return isoformat(ts)
    except OverflowError:
        return None


@dataclass
class NtfsBoot:
    bytes_per_sector: int
    sectors_per_cluster: int
    mft_cluster: int
    mft_record_size: int
    volume_size_sectors: int
    serial: int

    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster


def parse_ntfs_boot(sector: bytes) -> NtfsBoot | None:
    if len(sector) < 0x50 or sector[3:11] != NTFS_OEM:
        return None
    bps = struct.unpack_from("<H", sector, 0x0B)[0]
    spc = sector[0x0D]
    total_sectors = struct.unpack_from("<Q", sector, 0x28)[0]
    mft_cluster = struct.unpack_from("<Q", sector, 0x30)[0]
    clusters_per_record = struct.unpack_from("<b", sector, 0x40)[0]
    serial = struct.unpack_from("<Q", sector, 0x48)[0]
    if bps == 0 or spc == 0:
        return None
    cluster_size = bps * spc
    if clusters_per_record < 0:
        record_size = 1 << (-clusters_per_record)
    else:
        record_size = clusters_per_record * cluster_size
    if record_size <= 0:
        record_size = 1024
    return NtfsBoot(
        bytes_per_sector=bps,
        sectors_per_cluster=spc,
        mft_cluster=mft_cluster,
        mft_record_size=record_size,
        volume_size_sectors=total_sectors,
        serial=serial,
    )


def parse_runlist(data: bytes) -> list[tuple[int, int]]:
    """Return list of (length_in_clusters, start_cluster) runs. Sparse runs use start=-1."""
    runs: list[tuple[int, int]] = []
    offset = 0
    lcn = 0
    while offset < len(data):
        header = data[offset]
        offset += 1
        if header == 0:
            break
        len_size = header & 0x0F
        off_size = header >> 4
        if len_size == 0 or offset + len_size > len(data):
            break
        length = int.from_bytes(data[offset : offset + len_size], "little")
        offset += len_size
        if off_size == 0:
            runs.append((length, -1))
            continue
        if offset + off_size > len(data):
            break
        raw = data[offset : offset + off_size]
        offset += off_size
        rel = int.from_bytes(raw, "little", signed=True)
        lcn += rel
        runs.append((length, lcn))
    return runs


def _apply_usa(record: bytearray, usa_offset: int, usa_count: int) -> None:
    """Replace sector-end signatures with the Update Sequence Array values."""
    if usa_offset + 2 * usa_count > len(record) or usa_count < 2:
        return
    sector = 512
    for i in range(1, usa_count):
        pos = i * sector - 2
        if pos + 2 > len(record):
            break
        record[pos : pos + 2] = record[usa_offset + i * 2 : usa_offset + i * 2 + 2]


@dataclass
class NtfsScanResult:
    boot: NtfsBoot
    candidates: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class NtfsVolume:
    def __init__(self, source: ReadOnlySource, volume_offset: int, boot: NtfsBoot) -> None:
        self.source = source
        self.volume_offset = volume_offset
        self.boot = boot

    def _read_record(self, index: int) -> bytes:
        mft_off = self.volume_offset + self.boot.mft_cluster * self.boot.cluster_size
        return self.source.read(mft_off + index * self.boot.mft_record_size, self.boot.mft_record_size)

    def _read_runs(self, runs: list[tuple[int, int]], size: int) -> bytes:
        parts: list[bytes] = []
        remaining = size
        for length, start in runs:
            nbytes = length * self.boot.cluster_size
            if start < 0:
                chunk = bytes(min(nbytes, remaining))
            else:
                off = self.volume_offset + start * self.boot.cluster_size
                chunk = self.source.read(off, min(nbytes, remaining))
            parts.append(chunk)
            remaining -= len(chunk)
            if remaining <= 0:
                break
        data = b"".join(parts)
        return data[:size]

    def scan(self, *, include_existing: bool = False, max_records: int = 64_000) -> NtfsScanResult:
        notes: list[str] = ["NTFS journal / $LogFile is not replayed (read-only limitation)"]
        candidates: list[Candidate] = []
        # Record 0 is $MFT; use its DATA runlist when possible to iterate.
        rec0 = bytearray(self._read_record(0))
        if rec0[:4] != NTFS_FILE_RECORD_MAGIC:
            notes.append("MFT record 0 does not start with FILE; aborting NTFS metadata walk")
            return NtfsScanResult(boot=self.boot, notes=notes)
        records_to_scan = min(max_records, max(1, (self.boot.volume_size_sectors * self.boot.bytes_per_sector) // self.boot.mft_record_size // 4))
        # Prefer a hard cap derived from $MFT size if resident/non-resident DATA is readable.
        mft_size_hint = self._mft_data_size(rec0)
        if mft_size_hint:
            records_to_scan = min(records_to_scan, max(1, mft_size_hint // self.boot.mft_record_size))

        for index in range(records_to_scan):
            raw = bytearray(self._read_record(index))
            if raw[:4] != NTFS_FILE_RECORD_MAGIC:
                continue
            usa_off = struct.unpack_from("<H", raw, 0x04)[0]
            usa_count = struct.unpack_from("<H", raw, 0x06)[0]
            _apply_usa(raw, usa_off, usa_count)
            flags = struct.unpack_from("<H", raw, 0x16)[0]
            in_use = bool(flags & NTFS_FILE_IN_USE)
            is_dir = bool(flags & NTFS_FILE_DIRECTORY)
            if in_use and not include_existing:
                continue
            if is_dir:
                continue
            first_attr = struct.unpack_from("<H", raw, 0x14)[0]
            attrs = self._parse_attrs(bytes(raw), first_attr)
            names = [a["name"] for a in attrs if a["type"] == NTFS_ATTR_FILE_NAME and a.get("name")]
            name = names[-1] if names else f"mft_{index}"
            std = next((a for a in attrs if a["type"] == NTFS_ATTR_STANDARD_INFORMATION), None)
            data_attrs = [a for a in attrs if a["type"] == NTFS_ATTR_DATA]
            unnamed = [a for a in data_attrs if not a.get("attr_name")]
            ads = [a for a in data_attrs if a.get("attr_name")]
            primary = unnamed[0] if unnamed else (data_attrs[0] if data_attrs else None)
            content = b""
            size = 0
            offset = 0
            fragmented = False
            if primary:
                size = int(primary.get("size") or 0)
                if primary.get("resident"):
                    content = primary.get("data") or b""
                    size = len(content)
                else:
                    runs = primary.get("runs") or []
                    fragmented = len(runs) > 1
                    if runs and runs[0][1] >= 0:
                        offset = self.volume_offset + runs[0][1] * self.boot.cluster_size
                    try:
                        content = self._read_runs(runs, min(size, 16 * 1024 * 1024))
                    except Exception:
                        content = b""
            created = std.get("created") if std else None
            modified = std.get("modified") if std else None
            deleted = not in_use
            reasons = ["NTFS $MFT FILE record"]
            if deleted:
                reasons.append("in-use flag is clear (deleted or unused record)")
            if fragmented:
                reasons.append("non-resident $DATA has multiple runs")
            if ads:
                reasons.append(f"{len(ads)} alternate data stream(s) detected")
            confidence = 82.0 if not deleted else 68.0
            if not primary:
                confidence = 25.0
                reasons.append("no $DATA attribute")
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            extra = {
                "content": content,
                "fs": "ntfs",
                "mft_record": index,
                "ads": [a.get("attr_name") for a in ads],
            }
            candidates.append(
                Candidate(
                    id=new_id("ntfs-"),
                    name=name,
                    size=size,
                    file_type=ext or "bin",
                    mime="application/octet-stream",
                    method="existing" if in_use else "metadata",
                    status="existing" if in_use else "deleted",
                    source_offset=offset,
                    confidence=confidence,
                    confidence_reasons=reasons,
                    original_path=f"/{name}",
                    cluster_start=None,
                    extension=ext,
                    timestamps=TimestampSet(created=created, modified=modified),
                    is_fragmented=fragmented,
                    sha256=sha256_bytes(content) if content else None,
                    extra=extra,
                )
            )
        return NtfsScanResult(boot=self.boot, candidates=candidates, notes=notes)

    def _mft_data_size(self, rec0: bytearray) -> int | None:
        try:
            usa_off = struct.unpack_from("<H", rec0, 0x04)[0]
            usa_count = struct.unpack_from("<H", rec0, 0x06)[0]
            _apply_usa(rec0, usa_off, usa_count)
            first = struct.unpack_from("<H", rec0, 0x14)[0]
            for attr in self._parse_attrs(bytes(rec0), first):
                if attr["type"] == NTFS_ATTR_DATA and not attr.get("attr_name"):
                    return int(attr.get("size") or 0)
        except Exception:
            return None
        return None

    def _parse_attrs(self, record: bytes, first_offset: int) -> list[dict]:
        attrs: list[dict] = []
        offset = first_offset
        while 0 < offset + 8 <= len(record):
            atype = struct.unpack_from("<I", record, offset)[0]
            if atype == NTFS_ATTR_END:
                break
            alen = struct.unpack_from("<I", record, offset + 4)[0]
            if alen < 16 or offset + alen > len(record):
                break
            nonres = record[offset + 8]
            name_len = record[offset + 9]
            name_off = struct.unpack_from("<H", record, offset + 10)[0]
            attr_name = ""
            if name_len and name_off:
                attr_name = decode_utf16le(
                    record[offset + name_off : offset + name_off + name_len * 2]
                )
            parsed: dict = {"type": atype, "attr_name": attr_name, "resident": nonres == 0}
            if nonres == 0:
                content_len = struct.unpack_from("<I", record, offset + 16)[0]
                content_off = struct.unpack_from("<H", record, offset + 20)[0]
                data = record[offset + content_off : offset + content_off + content_len]
                parsed["data"] = data
                parsed["size"] = content_len
                if atype == NTFS_ATTR_FILE_NAME and len(data) >= 66:
                    nlen = data[64]
                    parsed["name"] = decode_utf16le(data[66 : 66 + nlen * 2])
                if atype == NTFS_ATTR_STANDARD_INFORMATION and len(data) >= 24:
                    created, modified = struct.unpack_from("<QQ", data, 0)
                    parsed["created"] = filetime_to_iso(created)
                    parsed["modified"] = filetime_to_iso(modified)
            else:
                start_vcn, end_vcn = struct.unpack_from("<QQ", record, offset + 16)
                run_off = struct.unpack_from("<H", record, offset + 32)[0]
                real_size = struct.unpack_from("<Q", record, offset + 48)[0] if offset + 56 <= len(record) else 0
                parsed["size"] = real_size
                parsed["runs"] = parse_runlist(record[offset + run_off : offset + alen])
                parsed["vcn"] = (start_vcn, end_vcn)
            attrs.append(parsed)
            offset += alen
        return attrs


def scan_ntfs(
    source: ReadOnlySource,
    volume_offset: int = 0,
    *,
    include_existing: bool = False,
    max_records: int = 64_000,
) -> NtfsScanResult | None:
    sector = source.read(volume_offset, 512)
    boot = parse_ntfs_boot(sector)
    if boot is None:
        return None
    return NtfsVolume(source, volume_offset, boot).scan(
        include_existing=include_existing, max_records=max_records
    )
