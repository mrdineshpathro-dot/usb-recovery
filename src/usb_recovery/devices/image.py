"""Disk-image source. Always treated as a file opened read-only."""

from __future__ import annotations

import os
from pathlib import Path

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.models import DeviceInfo, DeviceWarning
from usb_recovery.util import human_size


class ImageSource(ReadOnlySource):
    def info(self) -> DeviceInfo:
        path = Path(self.path)
        warnings: list[DeviceWarning] = []
        if not path.exists():
            warnings.append(
                DeviceWarning("missing", "Image file does not exist", "danger")
            )
        size = path.stat().st_size if path.exists() else 0
        if size == 0:
            warnings.append(DeviceWarning("empty", "Image file is empty", "warning"))
        return DeviceInfo(
            path=str(path.resolve()) if path.exists() else str(path),
            display_name=path.name,
            size_bytes=size,
            sector_size=self.sector_size,
            bus="image",
            removable=False,
            is_image=True,
            is_physical=False,
            read_only_open=True,
            warnings=warnings,
            extra={"kind": "disk-image", "human_size": human_size(size)},
        )

    def _discover_size(self) -> int:
        return os.path.getsize(self.path)
