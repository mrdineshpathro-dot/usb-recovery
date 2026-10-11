"""Split disk-image import (feature 261). Read-only concatenation of parts."""

from __future__ import annotations

import re
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import SourceAccessError
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.safety import open_readonly_fd
from usb_recovery.util import human_size

PART_RE = re.compile(r"^(?P<stem>.+?)(?:\.(?P<ext>dd|img|raw|bin))?\.(?P<n>\d{1,4})$", re.I)


def discover_parts(path: str | Path) -> list[Path]:
    p = Path(path)
    if p.is_dir():
        files = sorted(p.iterdir(), key=lambda x: x.name)
        return [f for f in files if f.is_file()]
    m = PART_RE.match(p.name)
    if not m:
        sibling = p.parent / (p.name + ".001")
        if sibling.exists():
            return discover_parts(sibling)
        return [p] if p.is_file() else []
    stem = m.group("stem")
    ext = m.group("ext")
    width = len(m.group("n"))
    parts: list[Path] = []
    n = 1
    while True:
        name = f"{stem}.{ext}.{n:0{width}d}" if ext else f"{stem}.{n:0{width}d}"
        candidate = p.parent / name
        if not candidate.is_file():
            # also try .001 starting at 0
            if n == 1:
                n = 0
                continue
            break
        parts.append(candidate)
        n += 1
        if n > 10_000:
            break
    return parts or ([p] if p.is_file() else [])


class SplitImageSource(ReadOnlySource):
    def __init__(self, path: str, sector_size: int = DEFAULT_SECTOR_SIZE) -> None:
        super().__init__(path, sector_size=sector_size)
        self.parts = discover_parts(path)
        if not self.parts:
            raise SourceAccessError(f"No split-image parts found for {path}")
        self._spans: list[tuple[int, int, Path]] = []
        self._fds: list[int] = []
        self._handles: list = []

    def open(self) -> None:
        if self._handles:
            return
        offset = 0
        for part in self.parts:
            fd = open_readonly_fd(part)
            handle = __import__("os").fdopen(fd, "rb", buffering=0)
            size = part.stat().st_size
            self._fds.append(fd)
            self._handles.append(handle)
            self._spans.append((offset, offset + size, part))
            offset += size
        self._size = offset
        self._handle = self._handles[0] if self._handles else None

    def close(self) -> None:
        for handle in self._handles:
            handle.close()
        self._handles = []
        self._fds = []
        self._handle = None

    def read(self, offset: int, size: int) -> bytes:
        if size < 0 or offset < 0:
            raise ValueError("offset and size must be non-negative")
        if not self._handles:
            self.open()
        if offset >= (self._size or 0):
            return b""
        size = min(size, (self._size or 0) - offset)
        out = bytearray()
        remaining = size
        cursor = offset
        for start, end, _part in self._spans:
            if cursor >= end or remaining <= 0:
                continue
            if cursor < start:
                continue
            local = cursor - start
            take = min(remaining, end - cursor)
            idx = self._spans.index((start, end, _part))
            handle = self._handles[idx]
            handle.seek(local)
            chunk = handle.read(take)
            out.extend(chunk)
            got = len(chunk)
            cursor += got
            remaining -= got
            if remaining <= 0:
                break
        return bytes(out)

    def info(self) -> DeviceInfo:
        return DeviceInfo(
            path=str(self.parts[0]),
            display_name=f"split image ({len(self.parts)} parts)",
            size_bytes=self.size,
            sector_size=self.sector_size,
            bus="image",
            is_image=True,
            extra={"parts": [str(p) for p in self.parts], "human_size": human_size(self.size)},
            warnings=[
                DeviceWarning("split", f"{len(self.parts)} parts concatenated read-only", "info")
            ],
        )

    def _discover_size(self) -> int:
        return sum(p.stat().st_size for p in self.parts)
