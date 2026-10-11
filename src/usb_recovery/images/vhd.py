"""Fixed VHD reader and VHDX/VHD container inspection (feature 262).

Dynamic/differencing VHD and full VHDX BAT translation are inspected, not
fully reconstructed. Fixed VHD (type 2) is readable as a raw disk.
"""

from __future__ import annotations

import struct
from pathlib import Path

from usb_recovery.constants import DEFAULT_SECTOR_SIZE
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.devices.image import ImageSource
from usb_recovery.exceptions import SourceAccessError, UnsupportedFilesystemError
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.util import human_size

VHD_COOKIE = b"conectix"
VHDX_SIG = b"vhdxfile"


def is_vhd(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 512:
        return False
    with open(p, "rb") as handle:
        handle.seek(-512, 2)
        return handle.read(8) == VHD_COOKIE


def is_vhdx(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 8:
        return False
    with open(p, "rb") as handle:
        return handle.read(8) == VHDX_SIG


def parse_vhd_footer(footer: bytes) -> dict:
    if len(footer) < 512 or footer[:8] != VHD_COOKIE:
        raise SourceAccessError("Not a VHD footer")
    disk_type = struct.unpack_from(">I", footer, 60)[0]
    current_size = struct.unpack_from(">Q", footer, 48)[0]
    cyl, heads, sectors = struct.unpack_from(">HBB", footer, 56)
    types = {2: "fixed", 3: "dynamic", 4: "differencing"}
    return {
        "kind": "vhd",
        "disk_type": types.get(disk_type, f"type-{disk_type}"),
        "type_id": disk_type,
        "current_size": current_size,
        "geometry": {"cylinders": cyl, "heads": heads, "sectors": sectors},
        "cookie": "conectix",
    }


def parse_vhdx_header(data: bytes) -> dict:
    if data[:8] != VHDX_SIG:
        raise SourceAccessError("Not a VHDX file")
    # Region table at 192 KiB typically; we report the identifier and file size.
    return {
        "kind": "vhdx",
        "signature": "vhdxfile",
        "note": "VHDX BAT translation is not fully implemented; use inspect + convert to raw when possible.",
    }


class VhdSource(ImageSource):
    """Read a *fixed* VHD as raw sectors, hiding the 512-byte footer."""

    def __init__(self, path: str, sector_size: int = DEFAULT_SECTOR_SIZE) -> None:
        super().__init__(path, sector_size=sector_size)
        self._meta: dict | None = None

    def open(self) -> None:
        super().open()
        if self._size is None or self._size < 512:
            raise SourceAccessError("VHD too small")
        footer = self.read(self._size - 512, 512) if self._handle else b""
        # After super().open, _size is full file size. Re-read footer via handle.
        assert self._handle is not None
        self._handle.seek(self._size - 512)
        footer = self._handle.read(512)
        self._meta = parse_vhd_footer(footer)
        if self._meta["type_id"] != 2:
            raise UnsupportedFilesystemError(
                f"VHD type {self._meta['disk_type']} is not a fixed disk; "
                "dynamic/differencing VHD is inspected only, not reconstructed."
            )
        self._size = self._size - 512

    def info(self) -> DeviceInfo:
        meta = self._meta or {}
        size = self._size or 0
        return DeviceInfo(
            path=self.path,
            display_name=Path(self.path).name,
            size_bytes=size,
            sector_size=self.sector_size,
            bus="image",
            is_image=True,
            extra={"container": meta, "human_size": human_size(size)},
            warnings=[DeviceWarning("vhd", "Fixed VHD; footer excluded from address space", "info")],
        )
