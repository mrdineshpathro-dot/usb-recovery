"""Format-specific structural checks. Failures lower confidence; they never write."""

from __future__ import annotations

import struct
import zlib
from typing import Callable

Validator = Callable[[bytes], tuple[bool, list[str]]]


def validate_jpeg(data: bytes) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return False, ["missing SOI"]
    i = 2
    found_sos = False
    found_eoi = False
    while i + 1 < len(data):
        if data[i] != 0xFF:
            if found_sos:
                eoi = data.find(b"\xff\xd9", i)
                found_eoi = eoi >= 0
                break
            notes.append("marker desync")
            return False, notes
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            if marker == 0xD9:
                found_eoi = True
                break
            continue
        if i + 2 > len(data):
            notes.append("truncated marker length")
            break
        length = struct.unpack_from(">H", data, i)[0]
        i += length
        if marker == 0xDA:
            found_sos = True
            eoi = data.find(b"\xff\xd9", i)
            found_eoi = eoi >= 0
            break
    if found_sos and found_eoi:
        return True, ["SOI/SOS/EOI present"]
    if found_sos:
        notes.append("SOS present but EOI missing — partial JPEG")
        return False, notes
    notes.append("no SOS marker")
    return False, notes


def validate_png(data: bytes) -> tuple[bool, list[str]]:
    sig = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(sig):
        return False, ["missing PNG signature"]
    offset = 8
    types: list[bytes] = []
    crc_ok = True
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        ctype = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            return False, ["truncated chunk"]
        crc_stored = struct.unpack_from(">I", data, end)[0]
        crc_calc = zlib.crc32(ctype + data[start:end]) & 0xFFFFFFFF
        if crc_stored != crc_calc:
            crc_ok = False
        types.append(ctype)
        offset = end + 4
        if ctype == b"IEND":
            break
    if not types or types[0] != b"IHDR":
        return False, ["first chunk is not IHDR"]
    if types[-1] != b"IEND":
        return False, ["missing IEND"]
    notes = ["IHDR and IEND present"]
    if not crc_ok:
        notes.append("one or more chunk CRCs failed")
        return False, notes
    return True, notes


def validate_pdf(data: bytes) -> tuple[bool, list[str]]:
    if not data.startswith(b"%PDF-"):
        return False, ["missing %PDF- header"]
    if b"%%EOF" in data[-2048:]:
        return True, ["header and %%EOF present"]
    if b"%%EOF" in data:
        return True, ["%%EOF present but not near the end"]
    return False, ["%%EOF missing — partial PDF"]


def validate_zip(data: bytes) -> tuple[bool, list[str]]:
    if not data.startswith(b"PK\x03\x04") and not data.startswith(b"PK\x05\x06"):
        return False, ["missing ZIP local file header"]
    eocd = data.rfind(b"PK\x05\x06")
    notes: list[str] = []
    if eocd < 0:
        return False, ["ZIP end-of-central-directory missing"]
    # OOXML detection
    if b"[Content_Types].xml" in data[: min(len(data), 1_000_000)]:
        notes.append("OOXML [Content_Types].xml present")
    notes.append("EOCD present")
    return True, notes


def validate_sqlite(data: bytes) -> tuple[bool, list[str]]:
    if not data.startswith(b"SQLite format 3\x00"):
        return False, ["missing SQLite magic"]
    if len(data) < 100:
        return False, ["header truncated"]
    page_size = struct.unpack_from(">H", data, 16)[0]
    if page_size == 1:
        page_size = 65536
    if page_size < 512 or (page_size & (page_size - 1)) != 0:
        return False, [f"invalid page size {page_size}"]
    return True, [f"SQLite header page size {page_size}"]


def validate_bmp(data: bytes) -> tuple[bool, list[str]]:
    if not data.startswith(b"BM") or len(data) < 26:
        return False, ["missing BM header"]
    size = struct.unpack_from("<I", data, 2)[0]
    if 14 < size <= len(data) + 1024:
        return True, ["BM header and size field plausible"]
    return False, ["BMP size field implausible"]


def validate_webp(data: bytes) -> tuple[bool, list[str]]:
    if len(data) < 16 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False, ["not a RIFF/WEBP header"]
    return True, ["RIFF WEBP"]


def validate_wav(data: bytes) -> tuple[bool, list[str]]:
    if len(data) < 16 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return False, ["not a RIFF/WAVE header"]
    return True, ["RIFF WAVE"]


def validate_avi(data: bytes) -> tuple[bool, list[str]]:
    if len(data) < 16 or data[0:4] != b"RIFF" or data[8:12] != b"AVI ":
        return False, ["not a RIFF/AVI header"]
    return True, ["RIFF AVI"]


def validate_mp4(data: bytes) -> tuple[bool, list[str]]:
    if len(data) < 12:
        return False, ["too short"]
    # box at 0: size(4) + 'ftyp'
    if data[4:8] == b"ftyp":
        return True, ["ftyp box at offset 0"]
    return False, ["no ftyp box"]


def validate_mp3(data: bytes) -> tuple[bool, list[str]]:
    if data.startswith(b"ID3"):
        return True, ["ID3 tag"]
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True, ["MPEG frame sync"]
    return False, ["no ID3 or frame sync"]


VALIDATORS: dict[str, Validator] = {
    "jpeg": validate_jpeg,
    "png": validate_png,
    "pdf": validate_pdf,
    "zip": validate_zip,
    "sqlite": validate_sqlite,
    "bmp": validate_bmp,
    "webp": validate_webp,
    "wav": validate_wav,
    "avi": validate_avi,
    "mp4": validate_mp4,
    "mp3": validate_mp3,
}


def run_validator(name: str | None, data: bytes) -> tuple[bool | None, list[str]]:
    if not name or name not in VALIDATORS:
        return None, []
    return VALIDATORS[name](data)
