"""Linux sysfs / udev-free removable device discovery and raw access."""

from __future__ import annotations

import os
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.util import human_size

SYS_BLOCK = Path("/sys/block")
DEV_ROOT = Path("/dev")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _read_int(path: Path, default: int = 0) -> int:
    text = _read_text(path)
    try:
        return int(text)
    except ValueError:
        return default


def _is_usb_device(sys_name: str) -> bool:
    device = SYS_BLOCK / sys_name / "device"
    try:
        resolved = device.resolve()
    except OSError:
        return False
    parts = str(resolved).split(os.sep)
    return "usb" in parts


def _logical_sector_size(sys_name: str) -> int:
    queue = SYS_BLOCK / sys_name / "queue"
    for candidate in ("logical_block_size", "hw_sector_size", "physical_block_size"):
        value = _read_int(queue / candidate, 0)
        if value:
            return value
    return DEFAULT_SECTOR_SIZE


def _mountpoints(dev_path: str) -> list[str]:
    mounts: list[str] = []
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 2 and (parts[0] == dev_path or parts[0].startswith(dev_path)):
                    mounts.append(parts[1])
    except OSError:
        return []
    return mounts


def linux_list_removable(include_non_usb: bool = False) -> list[DeviceInfo]:
    """Enumerate removable block devices. Loop and ram disks are skipped."""
    if not SYS_BLOCK.exists():
        return []
    devices: list[DeviceInfo] = []
    for entry in sorted(SYS_BLOCK.iterdir()):
        name = entry.name
        if name.startswith(("loop", "ram", "zram", "dm-", "md", "sr")):
            continue
        removable = _read_int(entry / "removable", 0) == 1
        usb = _is_usb_device(name)
        if not removable and not usb and not include_non_usb:
            continue
        size_sectors = _read_int(entry / "size", 0)
        sector = _logical_sector_size(name)
        size_bytes = size_sectors * 512  # /sys/block/*/size is always 512-byte units
        vendor = _read_text(entry / "device" / "vendor")
        model = _read_text(entry / "device" / "model")
        serial = _read_text(entry / "device" / "serial")
        rev = _read_text(entry / "device" / "rev")
        dev_path = str(DEV_ROOT / name)
        mounts = _mountpoints(dev_path)
        warnings: list[DeviceWarning] = []
        if mounts:
            warnings.append(
                DeviceWarning(
                    "mounted",
                    "Volume is mounted at "
                    + ", ".join(mounts)
                    + ". Unmount it before acquisition; a live mount may cause writes.",
                    "danger",
                )
            )
        if size_bytes == 0:
            warnings.append(DeviceWarning("zero-size", "Device reports zero size", "warning"))
        if not usb:
            warnings.append(
                DeviceWarning(
                    "not-usb",
                    "Device does not appear on a USB bus. Confirm you selected the pen drive.",
                    "warning",
                )
            )
        display = " ".join(p for p in (vendor, model) if p) or name
        devices.append(
            DeviceInfo(
                path=dev_path,
                display_name=f"{display} ({name})",
                size_bytes=size_bytes,
                sector_size=sector,
                bus="usb" if usb else "block",
                removable=removable,
                vendor=vendor,
                model=model,
                serial=serial,
                revision=rev,
                mountpoints=mounts,
                is_image=False,
                is_physical=True,
                read_only_open=True,
                warnings=warnings,
                extra={
                    "sysfs": str(entry),
                    "human_size": human_size(size_bytes),
                    "sys_size_sectors": size_sectors,
                },
            )
        )
    return devices


class LinuxBlockSource(ReadOnlySource):
    def __init__(self, path: str, sector_size: int | None = None) -> None:
        name = Path(path).name
        sector = sector_size or _logical_sector_size(name) or DEFAULT_SECTOR_SIZE
        super().__init__(path, sector_size=sector)

    def info(self) -> DeviceInfo:
        listed = {d.path: d for d in linux_list_removable(include_non_usb=True)}
        if self.path in listed:
            return listed[self.path]
        size = self._discover_size() if self._handle else 0
        return DeviceInfo(
            path=self.path,
            display_name=Path(self.path).name,
            size_bytes=size,
            sector_size=self.sector_size,
            bus="block",
            is_physical=True,
            extra={"human_size": human_size(size)},
        )

    def _discover_size(self) -> int:
        name = Path(self.path).name
        sys_size = _read_int(SYS_BLOCK / name / "size", 0)
        if sys_size:
            return sys_size * 512
        if self._handle is not None:
            self._handle.seek(0, os.SEEK_END)
            return int(self._handle.tell())
        return 0
