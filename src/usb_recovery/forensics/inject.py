"""Failure-injection helpers (357)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import DestinationError, SourceAccessError


class FailureInjector:
    """Wrap a read-only source and inject read errors / disconnects."""

    def __init__(
        self,
        inner: ReadOnlySource,
        *,
        fail_offsets: set[int] | None = None,
        disconnect_after: int | None = None,
    ) -> None:
        self.inner = inner
        self.fail_offsets = fail_offsets or set()
        self.disconnect_after = disconnect_after
        self.reads = 0

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def read(self, offset: int, size: int) -> bytes:
        self.reads += 1
        if self.disconnect_after is not None and self.reads > self.disconnect_after:
            raise SourceAccessError("injected device disconnection")
        if offset in self.fail_offsets:
            raise OSError("injected EIO")
        return self.inner.read(offset, size)


def simulate_disk_full(dest: str | Path, needed: int, free: int = 0) -> None:
    if free < needed:
        raise DestinationError(f"injected disk-full: need {needed} have {free}")


def malformed_image(path: str | Path, *, kind: str = "truncated-fat") -> Path:
    """Write a deliberately malformed image for parser tests. Destination only."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if kind == "truncated-fat":
        boot = bytearray(64)  # too short for a full sector
        boot[0:3] = b"\xeb\x3c\x90"
        boot[3:11] = b"MSDOS5.0"
        dest.write_bytes(bytes(boot))
    elif kind == "garbage":
        dest.write_bytes(b"\xff" * 512)
    elif kind == "partial-mbr":
        dest.write_bytes(b"\x00" * 510)  # missing 55AA
    else:
        dest.write_bytes(b"")
    return dest
