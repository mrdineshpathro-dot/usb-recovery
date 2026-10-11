"""Pure helpers used across acquisition, parsing, and recovery."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(ts: datetime | None = None) -> str:
    value = ts or utcnow()
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str = "") -> str:
    token = uuid.uuid4().hex
    return f"{prefix}{token}" if prefix else token


def human_size(num: int | float) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num} B"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str], chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_at(handle: BinaryIO, offset: int, size: int) -> bytes:
    """Read exactly `size` bytes from `offset`, or fewer at EOF. Never writes."""
    handle.seek(offset)
    return handle.read(size)


def chunks(length: int, size: int) -> Iterator[tuple[int, int]]:
    """Yield (offset, this_size) covering 0..length."""
    offset = 0
    while offset < length:
        this = min(size, length - offset)
        yield offset, this
        offset += this


def align_down(value: int, alignment: int) -> int:
    if alignment <= 0:
        return value
    return value - (value % alignment)


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0:
        return value
    remainder = value % alignment
    return value if remainder == 0 else value + (alignment - remainder)


def decode_ascii(data: bytes, fallback: str = ".") -> str:
    chars: list[str] = []
    for byte in data:
        chars.append(chr(byte) if 32 <= byte < 127 else fallback)
    return "".join(chars)


def decode_utf16le(data: bytes) -> str:
    try:
        text = data.decode("utf-16le", errors="replace")
    except Exception:
        return ""
    return text.split("\x00", 1)[0]


def dos_datetime(dos_date: int, dos_time: int) -> datetime | None:
    """Decode MS-DOS date/time. Returns None for zeros or invalid fields."""
    if dos_date == 0 and dos_time == 0:
        return None
    year = ((dos_date >> 9) & 0x7F) + 1980
    month = (dos_date >> 5) & 0x0F
    day = dos_date & 0x1F
    hour = (dos_time >> 11) & 0x1F
    minute = (dos_time >> 5) & 0x3F
    second = (dos_time & 0x1F) * 2
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None


def safe_filename(name: str, fallback: str = "unnamed") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip(" .")
    return cleaned or fallback


def unique_path(dest_dir: Path, filename: str, template: str = "{stem} ({n}){suffix}") -> Path:
    """Return dest_dir/filename, adding (n) if the path already exists."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    n = 1
    while True:
        alt = dest_dir / template.format(stem=stem, n=n, suffix=suffix)
        if not alt.exists():
            return alt
        n += 1
        if n > 10_000:
            return dest_dir / f"{stem}-{new_id()}{suffix}"


def iter_overlapping_windows(
    length: int, window: int, overlap: int
) -> Iterable[tuple[int, int]]:
    """Windows covering `length` with `overlap` so signatures on boundaries are seen."""
    if window <= 0:
        return
    step = max(1, window - max(0, overlap))
    offset = 0
    while offset < length:
        size = min(window, length - offset)
        yield offset, size
        if offset + size >= length:
            break
        offset += step


def file_device_id(path: str | os.PathLike[str]) -> tuple[int, int] | None:
    """Return (st_dev, st_ino) or (st_dev, 0) for the path. None if it does not exist."""
    try:
        st = os.stat(path, follow_symlinks=True)
    except OSError:
        return None
    return (st.st_dev, getattr(st, "st_ino", 0))


def parent_existing(path: str | os.PathLike[str]) -> Path:
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return p
