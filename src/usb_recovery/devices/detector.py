"""Cross-platform device listing and source factory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.devices.image import ImageSource
from usb_recovery.devices.linux import LinuxBlockSource, linux_list_removable
from usb_recovery.devices.windows import WindowsBlockSource, windows_list_removable
from usb_recovery.exceptions import SourceAccessError
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.safety import is_block_device, require_device_confirmation


def list_devices(*, include_non_usb: bool = False) -> list[DeviceInfo]:
    if sys.platform.startswith("linux"):
        return linux_list_removable(include_non_usb=include_non_usb)
    if sys.platform == "win32":
        return windows_list_removable()
    return []


def probe_image(path: str | os.PathLike[str]) -> DeviceInfo:
    source = ImageSource(str(path))
    return source.info()


def open_source(
    path: str | os.PathLike[str],
    *,
    confirm: str | None = None,
    sector_size: int | None = None,
) -> ReadOnlySource:
    """Open a disk image or physical device read-only.

    Physical devices require `confirm` equal to DEVICE_CONFIRM_TOKEN.
    """
    raw = os.fspath(path)
    physical = is_block_device(raw) or _looks_like_windows_device(raw)
    if physical:
        require_device_confirmation(confirm, is_physical=True)
        source: ReadOnlySource
        if sys.platform == "win32":
            source = WindowsBlockSource(raw, sector_size=sector_size or DEFAULT_SECTOR_SIZE)
        else:
            source = LinuxBlockSource(raw, sector_size=sector_size)
        source.open()
        return source

    file_path = Path(raw)
    if not file_path.is_file() and not file_path.is_dir():
        raise SourceAccessError(
            f"{raw} is neither a readable file nor a block device. "
            "Pass a disk image path or a device such as /dev/sdb."
        )
    from usb_recovery.images.compressed import GzipImageSource, is_gzip
    from usb_recovery.images.split import SplitImageSource, discover_parts
    from usb_recovery.images.vhd import VhdSource, is_vhd

    sector = sector_size or DEFAULT_SECTOR_SIZE
    if file_path.is_file() and is_gzip(file_path):
        source = GzipImageSource(str(file_path), sector_size=sector)
        source.open()
        return source
    if file_path.is_file() and is_vhd(file_path):
        source = VhdSource(str(file_path), sector_size=sector)
        source.open()
        return source
    parts = discover_parts(file_path)
    if len(parts) > 1:
        source = SplitImageSource(str(file_path), sector_size=sector)
        source.open()
        return source
    if not file_path.is_file():
        raise SourceAccessError(f"{raw} is not a readable image file")
    source = ImageSource(str(file_path), sector_size=sector)
    source.open()
    return source


def _looks_like_windows_device(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith("\\\\.\\") or lowered.startswith("\\\\.\\physicaldrive")


def describe_source(path: str, *, confirm: str | None = None) -> DeviceInfo:
    """Return DeviceInfo without leaving a handle open longer than needed."""
    if Path(path).is_file():
        info = probe_image(path)
        if info.size_bytes % DEFAULT_SECTOR_SIZE:
            info.warnings.append(
                DeviceWarning(
                    "unaligned",
                    "Image size is not a multiple of 512 bytes; trailing bytes are ignored.",
                    "info",
                )
            )
        return info
    source = open_source(path, confirm=confirm)
    try:
        return source.info()
    finally:
        source.close()
