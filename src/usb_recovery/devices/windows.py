r"""Windows removable-device discovery via ctypes (no pywin32 required).

Physical access uses ``\\.\PhysicalDriveN`` or ``\\.\X:`` opened with
GENERIC_READ. Administrator rights are typically required for physical drives.
This module is imported on non-Windows platforms so unit tests can mock it;
live enumeration is a no-op outside Windows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.util import human_size

DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0


def _kernel32():  # pragma: no cover - windows only
    import ctypes

    return ctypes.windll.kernel32  # type: ignore[attr-defined]


def windows_list_removable() -> list[DeviceInfo]:
    if sys.platform != "win32":
        return []
    return _enumerate_win32()


def _enumerate_win32() -> list[DeviceInfo]:  # pragma: no cover - needs Windows
    import ctypes
    import string

    k32 = _kernel32()
    mask = k32.GetLogicalDrives()
    devices: list[DeviceInfo] = []
    for i, letter in enumerate(string.ascii_uppercase):
        if not (mask & (1 << i)):
            continue
        root = f"{letter}:\\"
        dtype = k32.GetDriveTypeW(root)
        if dtype not in (DRIVE_REMOVABLE,):
            continue
        volume_name = ctypes.create_unicode_buffer(261)
        fs_name = ctypes.create_unicode_buffer(261)
        serial = ctypes.c_uint(0)
        k32.GetVolumeInformationW(
            root,
            volume_name,
            261,
            ctypes.byref(serial),
            None,
            None,
            fs_name,
            261,
        )
        free = ctypes.c_ulonglong(0)
        total = ctypes.c_ulonglong(0)
        k32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), ctypes.byref(free))
        warnings: list[DeviceWarning] = [
            DeviceWarning(
                "live-volume",
                "Windows volumes are typically mounted. Prefer imaging "
                f"{letter}: after using the OS to eject write access, or open "
                r"\\.\PhysicalDriveN as Administrator.",
                "warning",
            )
        ]
        devices.append(
            DeviceInfo(
                path=f"\\\\.\\{letter}:",
                display_name=f"{letter}: {volume_name.value or 'Removable'}",
                size_bytes=int(total.value),
                sector_size=DEFAULT_SECTOR_SIZE,
                bus="usb",
                removable=True,
                filesystem_hint=fs_name.value or None,
                mountpoints=[root],
                is_physical=True,
                serial=f"{serial.value:08X}" if serial.value else "",
                warnings=warnings,
                extra={"human_size": human_size(int(total.value)), "letter": letter},
            )
        )
    return devices


class WindowsBlockSource(ReadOnlySource):
    def info(self) -> DeviceInfo:
        listed = {d.path: d for d in windows_list_removable()}
        if self.path in listed:
            return listed[self.path]
        return DeviceInfo(
            path=self.path,
            display_name=Path(self.path).name,
            size_bytes=self._size or 0,
            sector_size=self.sector_size,
            bus="windows",
            is_physical=True,
        )

    def _discover_size(self) -> int:
        if self._handle is None:
            return 0
        try:
            self._handle.seek(0, os.SEEK_END)
            return int(self._handle.tell())
        except OSError:
            return 0
