"""Filesystem image that begins at a nonzero byte/sector offset (266)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import DeviceInfo, DeviceWarning


class OffsetSource(ReadOnlySource):
    """Wrap another source so offset 0 is `base` bytes into the inner image."""

    def __init__(self, inner: ReadOnlySource, base: int) -> None:
        super().__init__(inner.path, sector_size=inner.sector_size)
        if base < 0:
            raise ValueError("base offset must be >= 0")
        self.inner = inner
        self.base = base

    def open(self) -> None:
        self.inner.open()
        self._size = max(0, self.inner.size - self.base)
        self._handle = self.inner._handle

    def close(self) -> None:
        self.inner.close()
        self._handle = None

    def read(self, offset: int, size: int) -> bytes:
        return self.inner.read(self.base + offset, size)

    def info(self) -> DeviceInfo:
        info = self.inner.info()
        info.size_bytes = self.size
        info.warnings = list(info.warnings) + [
            DeviceWarning("offset", f"Logical offset 0 maps to byte {self.base} of the container", "info")
        ]
        info.extra = dict(info.extra)
        info.extra["image_offset"] = self.base
        return info

    def _discover_size(self) -> int:
        return max(0, self.inner.size - self.base)
