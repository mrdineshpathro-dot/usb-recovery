from __future__ import annotations

from usb_recovery.constants import EXFAT_OEM, NTFS_OEM
from usb_recovery.filesystems.identifier import identify_boot_sector


def test_ntfs_oem() -> None:
    sector = bytearray(512)
    sector[3:11] = NTFS_OEM
    sector[0x0B:0x0D] = (512).to_bytes(2, "little")
    sector[0x0D] = 8
    assert identify_boot_sector(bytes(sector)) == "ntfs"


def test_exfat_oem() -> None:
    sector = bytearray(512)
    sector[3:11] = EXFAT_OEM
    assert identify_boot_sector(bytes(sector)) == "exfat"


def test_unknown() -> None:
    assert identify_boot_sector(b"\x00" * 512) is None
