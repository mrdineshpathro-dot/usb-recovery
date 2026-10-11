"""Compressed image reader (feature 264). gzip without writing an extracted file.

Random access is provided by decompressing into a memory buffer. Images larger
than `max_ram` must be converted to raw on a destination disk first.
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import SourceAccessError
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.util import human_size

DEFAULT_MAX_RAM = 512 * 1024 * 1024


def is_gzip(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    with open(p, "rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


class GzipImageSource(ReadOnlySource):
    def __init__(
        self,
        path: str,
        sector_size: int = DEFAULT_SECTOR_SIZE,
        *,
        max_ram: int = DEFAULT_MAX_RAM,
    ) -> None:
        super().__init__(path, sector_size=sector_size)
        self.max_ram = max_ram
        self._buffer: io.BytesIO | None = None

    def open(self) -> None:
        if self._buffer is not None:
            return
        src = Path(self.path)
        if src.stat().st_size > self.max_ram:
            raise SourceAccessError(
                f"gzip image {src} is larger than the in-memory cap "
                f"({human_size(self.max_ram)}). Convert to raw on another disk first."
            )
        with gzip.open(src, "rb") as handle:
            data = handle.read(self.max_ram + 1)
        if len(data) > self.max_ram:
            raise SourceAccessError("Decompressed image exceeds in-memory cap")
        self._buffer = io.BytesIO(data)
        self._size = len(data)
        self._handle = self._buffer  # type: ignore[assignment]

    def close(self) -> None:
        self._buffer = None
        self._handle = None

    def info(self) -> DeviceInfo:
        size = self._size or 0
        return DeviceInfo(
            path=self.path,
            display_name=Path(self.path).name,
            size_bytes=size,
            sector_size=self.sector_size,
            bus="image",
            is_image=True,
            extra={"container": "gzip", "human_size": human_size(size)},
            warnings=[
                DeviceWarning(
                    "gzip",
                    "Decompressed in RAM only; the gzip file on disk is never modified.",
                    "info",
                )
            ],
        )

    def _discover_size(self) -> int:
        if self._size is None:
            self.open()
        return self._size or 0
