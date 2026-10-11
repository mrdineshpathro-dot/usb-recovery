from __future__ import annotations

from usb_recovery.filesystems.ntfs import parse_ntfs_boot, parse_runlist
from usb_recovery.constants import NTFS_OEM


def test_parse_boot() -> None:
    sector = bytearray(512)
    sector[3:11] = NTFS_OEM
    sector[0x0B:0x0D] = (512).to_bytes(2, "little")
    sector[0x0D] = 8
    sector[0x28:0x30] = (100000).to_bytes(8, "little")
    sector[0x30:0x38] = (4).to_bytes(8, "little")
    sector[0x40] = 0xF6  # 2^-(-10)? actually -10 -> 1024. Use signed.
    sector[0x40] = (-10) & 0xFF
    boot = parse_ntfs_boot(bytes(sector))
    assert boot is not None
    assert boot.mft_record_size == 1024
    assert boot.cluster_size == 4096


def test_runlist() -> None:
    # length size 1, offset size 1: length=4, rel=+10
    data = bytes([0x11, 0x04, 0x0A, 0x00])
    runs = parse_runlist(data)
    assert runs[0] == (4, 10)
