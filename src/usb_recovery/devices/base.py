"""Read-only source abstraction for block devices and disk images."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import BinaryIO

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.exceptions import SourceAccessError
from usb_recovery.models import DeviceInfo
from usb_recovery.safety import assert_fd_read_only, open_readonly_fd


class ReadOnlySource(ABC):
    """Sector-addressable source that is opened read-only."""

    def __init__(self, path: str, sector_size: int = DEFAULT_SECTOR_SIZE) -> None:
        self.path = path
        self._sector_size = sector_size
        self._fd: int | None = None
        self._handle: BinaryIO | None = None
        self._size: int | None = None

    @property
    def sector_size(self) -> int:
        return self._sector_size

    def open(self) -> None:
        if self._handle is not None:
            return
        try:
            fd = open_readonly_fd(self.path)
            assert_fd_read_only(fd)
            # buffering=0 so seek/read offsets match the device.
            handle = os.fdopen(fd, "rb", buffering=0)
        except OSError as exc:
            raise SourceAccessError(f"Cannot open {self.path} read-only: {exc}") from exc
        self._fd = fd
        self._handle = handle
        self._size = self._discover_size()

    def close(self) -> None:
        handle, self._handle = self._handle, None
        self._fd = None
        if handle is not None:
            handle.close()

    def __enter__(self) -> "ReadOnlySource":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def size(self) -> int:
        if self._size is None:
            self.open()
        assert self._size is not None
        return self._size

    def read(self, offset: int, size: int) -> bytes:
        if size < 0 or offset < 0:
            raise ValueError("offset and size must be non-negative")
        if self._handle is None:
            self.open()
        assert self._handle is not None
        if offset >= self.size:
            return b""
        size = min(size, self.size - offset)
        self._handle.seek(offset)
        data = self._handle.read(size)
        return data

    def read_sector(self, lba: int, count: int = 1) -> bytes:
        return self.read(lba * self.sector_size, count * self.sector_size)

    @abstractmethod
    def info(self) -> DeviceInfo:
        raise NotImplementedError

    @abstractmethod
    def _discover_size(self) -> int:
        raise NotImplementedError
