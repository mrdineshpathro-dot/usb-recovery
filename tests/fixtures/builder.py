"""Synthetic disk-image builders used by the test suite. No real devices needed."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def minimal_jpeg(payload: bytes = b"USB-RECOVERY") -> bytes:
    # SOI, APP0, SOF0 (tiny), SOS, payload, EOI — structurally valid enough for our validator.
    soi = b"\xff\xd8"
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    dht = b"\xff\xc4" + struct.pack(">H", 20) + b"\x00" + bytes(16) + b"\x00"
    sos = b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
    return soi + app0 + sof + dht + sos + payload + b"\xff\xd9"


def minimal_png(width: int = 1, height: int = 1) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", _crc(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Empty IDAT is invalid for viewers but our validator only checks CRC + IHDR/IEND.
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def minimal_pdf(text: str = "USB Recovery Lab") -> bytes:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R >>endobj\n"
        + f"4 0 obj<< /Length {len(text)} >>stream\n{text}\nendstream\nendobj\n".encode()
        + b"%%EOF\n"
    )
    return body


def minimal_zip(name: str = "readme.txt", payload: bytes = b"hello") -> bytes:
    name_b = name.encode("utf-8")
    crc = _crc(payload)
    local = (
        b"PK\x03\x04"
        + struct.pack("<HHHHHIIIHH", 20, 0, 0, 0, 0, crc, len(payload), len(payload), len(name_b), 0)
        + name_b
        + payload
    )
    central = (
        b"PK\x01\x02"
        + struct.pack("<HHHHHHIIIHHHHHII", 20, 20, 0, 0, 0, 0, crc, len(payload), len(payload), len(name_b), 0, 0, 0, 0, 0, 0)
        + name_b
    )
    eocd = (
        b"PK\x05\x06"
        + struct.pack("<HHHHIIH", 0, 0, 1, 1, len(central), len(local), 0)
    )
    return local + central + eocd


def _fat16_boot(total_sectors: int, bps: int = 512, spc: int = 1, reserved: int = 1, fats: int = 2, root_entries: int = 512) -> bytes:
    fat_sz = 32  # enough for a few thousand clusters
    boot = bytearray(bps)
    boot[0:3] = b"\xeb\x3c\x90"
    boot[3:11] = b"MSDOS5.0"
    struct.pack_into("<H", boot, 0x0B, bps)
    boot[0x0D] = spc
    struct.pack_into("<H", boot, 0x0E, reserved)
    boot[0x10] = fats
    struct.pack_into("<H", boot, 0x11, root_entries)
    if total_sectors < 0x10000:
        struct.pack_into("<H", boot, 0x13, total_sectors)
    else:
        struct.pack_into("<I", boot, 0x20, total_sectors)
    boot[0x15] = 0xF8
    struct.pack_into("<H", boot, 0x16, fat_sz)
    struct.pack_into("<H", boot, 0x18, 32)
    struct.pack_into("<H", boot, 0x1A, 2)
    boot[0x36:0x3E] = b"FAT16   "
    boot[0x1FE:0x200] = b"\x55\xAA"
    return bytes(boot)


def _dir_entry(name83: bytes, cluster: int, size: int, attr: int = 0x20, deleted: bool = False) -> bytes:
    raw = bytearray(32)
    raw[0:11] = name83.ljust(11, b" ")[:11]
    if deleted:
        raw[0] = 0xE5
    raw[0x0B] = attr
    struct.pack_into("<H", raw, 0x1A, cluster & 0xFFFF)
    struct.pack_into("<I", raw, 0x1C, size)
    # 2024-01-02 12:00 DOS date/time
    struct.pack_into("<H", raw, 0x18, (44 << 9) | (1 << 5) | 2)
    struct.pack_into("<H", raw, 0x16, (12 << 11))
    return bytes(raw)


def build_fat16_image(path: Path) -> dict:
    """Create a 4 MiB FAT16 super-floppy with live, deleted, and carved files."""
    bps = 512
    spc = 1
    reserved = 1
    fats = 2
    fat_sz = 32
    root_entries = 512
    root_sectors = (root_entries * 32) // bps
    total_sectors = 8192  # 4 MiB so cluster count is FAT16 (>= 4085)
    image = bytearray(total_sectors * bps)
    image[0:bps] = _fat16_boot(total_sectors, bps, spc, reserved, fats, root_entries)

    fat_off = reserved * bps
    fat = bytearray(fat_sz * bps)
    struct.pack_into("<HH", fat, 0, 0xFFF8, 0xFFFF)  # media + EOC for cluster 1

    def set_fat(cluster: int, value: int) -> None:
        struct.pack_into("<H", fat, cluster * 2, value)

    root_off = fat_off + fats * fat_sz * bps
    data_off = root_off + root_sectors * bps

    def cluster_off(c: int) -> int:
        return data_off + (c - 2) * bps * spc

    hello = b"Hello, USB Recovery Lab\n"
    jpeg = minimal_jpeg()
    secret = b"deleted-secret-payload-42\n"
    png = minimal_png()

    # cluster 2: HELLO.TXT (live)
    set_fat(2, 0xFFFF)
    image[cluster_off(2) : cluster_off(2) + len(hello)] = hello
    # cluster 3: PHOTO.JPG (live)
    set_fat(3, 0xFFFF)
    image[cluster_off(3) : cluster_off(3) + len(jpeg)] = jpeg
    # cluster 4: SECRET.TXT then mark deleted, chain left intact
    set_fat(4, 0xFFFF)
    image[cluster_off(4) : cluster_off(4) + len(secret)] = secret
    # cluster 5: leftover PNG with no directory entry (carve-only)
    image[cluster_off(5) : cluster_off(5) + len(png)] = png
    # cluster 6: GONE.TXT deleted AND fat zeroed (contiguous heuristic)
    orphan = b"orphan-content\n"
    image[cluster_off(6) : cluster_off(6) + len(orphan)] = orphan
    # fat entry 6 stays 0

    image[fat_off : fat_off + len(fat)] = fat
    image[fat_off + fat_sz * bps : fat_off + 2 * fat_sz * bps] = fat

    entries = (
        _dir_entry(b"HELLO   TXT", 2, len(hello), deleted=False)
        + _dir_entry(b"PHOTO   JPG", 3, len(jpeg), deleted=False)
        + _dir_entry(b"SECRET  TXT", 4, len(secret), deleted=True)
        + _dir_entry(b"GONE    TXT", 6, len(orphan), deleted=True)
    )
    image[root_off : root_off + len(entries)] = entries

    path.write_bytes(bytes(image))
    return {
        "path": path,
        "size": len(image),
        "hello": hello,
        "jpeg": jpeg,
        "secret": secret,
        "png": png,
        "hello_cluster": 2,
        "data_offset": data_off,
        "bps": bps,
    }


def build_mbr_fat_image(path: Path) -> dict:
    """MBR with one FAT16 partition starting at LBA 8 (4 KiB)."""
    inner = Path(str(path) + ".inner")
    meta = build_fat16_image(inner)
    inner_bytes = inner.read_bytes()
    prefix = 8 * 512
    image = bytearray(prefix + len(inner_bytes))
    image[prefix:] = inner_bytes
    # MBR
    image[0:3] = b"\xeb\x00\x90"
    entry = bytearray(16)
    entry[0] = 0x80
    entry[4] = 0x0E  # FAT16 LBA
    struct.pack_into("<I", entry, 8, 8)
    struct.pack_into("<I", entry, 12, len(inner_bytes) // 512)
    image[446:462] = entry
    image[510:512] = b"\x55\xAA"
    path.write_bytes(bytes(image))
    inner.unlink()
    meta["path"] = path
    meta["partition_lba"] = 8
    return meta


def build_gpt_empty_image(path: Path, sectors: int = 256) -> dict:
    """Minimal GPT with one Microsoft basic-data partition covering most of the disk."""
    bps = 512
    image = bytearray(sectors * bps)
    # Protective MBR
    entry = bytearray(16)
    entry[4] = 0xEE
    struct.pack_into("<I", entry, 8, 1)
    struct.pack_into("<I", entry, 12, sectors - 1)
    image[446:462] = entry
    image[510:512] = b"\x55\xAA"

    def gpt_header(current: int, backup: int, part_lba: int) -> bytes:
        hdr = bytearray(bps)
        hdr[0:8] = b"EFI PART"
        struct.pack_into("<I", hdr, 8, 0x00010000)
        struct.pack_into("<I", hdr, 12, 92)
        struct.pack_into("<Q", hdr, 24, current)
        struct.pack_into("<Q", hdr, 32, backup)
        struct.pack_into("<Q", hdr, 40, 34)
        struct.pack_into("<Q", hdr, 48, sectors - 34)
        hdr[56:72] = bytes(16)  # disk guid zeros ok for tests
        hdr[56] = 0x11
        struct.pack_into("<Q", hdr, 72, part_lba)
        struct.pack_into("<I", hdr, 80, 128)
        struct.pack_into("<I", hdr, 84, 128)
        return bytes(hdr)

    image[bps : 2 * bps] = gpt_header(1, sectors - 1, 2)
    # one partition entry at LBA 2
    ent = bytearray(128)
    # Microsoft basic data GUID little-endian
    import uuid

    guid = uuid.UUID("EBD0A0A2-B9E5-4433-87C0-68B6B72699C7")
    ent[0:16] = guid.bytes_le
    ent[16:32] = uuid.UUID("12345678-1234-1234-1234-1234567890AB").bytes_le
    struct.pack_into("<Q", ent, 32, 34)
    struct.pack_into("<Q", ent, 40, sectors - 34)
    name = "DATA".encode("utf-16le")
    ent[56 : 56 + len(name)] = name
    image[2 * bps : 2 * bps + 128] = ent
    image[(sectors - 1) * bps : sectors * bps] = gpt_header(sectors - 1, 1, sectors - 33)
    path.write_bytes(bytes(image))
    return {"path": path, "sectors": sectors}


def build_carve_image(path: Path) -> dict:
    jpeg = minimal_jpeg(b"carve-jpeg")
    png = minimal_png()
    pdf = minimal_pdf()
    zipped = minimal_zip()
    blob = bytearray(64 * 1024)
    blob[1024 : 1024 + len(jpeg)] = jpeg
    blob[8192 : 8192 + len(png)] = png
    blob[16384 : 16384 + len(pdf)] = pdf
    blob[32768 : 32768 + len(zipped)] = zipped
    path.write_bytes(bytes(blob))
    return {"path": path, "jpeg": jpeg, "png": png, "pdf": pdf, "zip": zipped}
