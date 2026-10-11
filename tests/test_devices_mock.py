from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from usb_recovery.devices.detector import list_devices, open_source
from usb_recovery.devices.linux import linux_list_removable
from usb_recovery.exceptions import SourceAccessError
from usb_recovery.models import DeviceInfo


def test_open_image(tmp_path: Path) -> None:
    img = tmp_path / "disk.img"
    img.write_bytes(b"\x00" * 1024)
    src = open_source(str(img))
    try:
        assert src.size == 1024
        assert src.read(0, 4) == b"\x00\x00\x00\x00"
        info = src.info()
        assert info.is_image
        assert not info.is_physical
    finally:
        src.close()


def test_open_missing() -> None:
    try:
        open_source("/tmp/definitely-missing-usb-recovery-lab.img")
        assert False, "should have raised"
    except SourceAccessError:
        pass


def test_linux_list_uses_sysfs(tmp_path: Path, monkeypatch) -> None:
    # When /sys/block is missing the helper returns [].
    with patch("usb_recovery.devices.linux.SYS_BLOCK", Path("/no/such/sys/block")):
        assert linux_list_removable() == []


def test_list_devices_linux_mocked() -> None:
    fake = [
        DeviceInfo(
            path="/dev/sdb",
            display_name="USB Stick",
            size_bytes=8_000_000,
            sector_size=512,
            bus="usb",
            removable=True,
            is_physical=True,
        )
    ]
    with patch("usb_recovery.devices.detector.linux_list_removable", return_value=fake):
        with patch("usb_recovery.devices.detector.sys") as sysmod:
            sysmod.platform = "linux"
            found = list_devices()
    assert found[0].path == "/dev/sdb"
