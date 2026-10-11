from __future__ import annotations

import struct

from usb_recovery.constants import EXFAT_OEM
from usb_recovery.filesystems.exfat import parse_exfat_boot


def test_parse_exfat_boot() -> None:
    sector = bytearray(512)
    sector[3:11] = EXFAT_OEM
    struct.pack_into("<QQ", sector, 64, 0, 100000)
    struct.pack_into("<IIIII", sector, 80, 24, 128, 152, 1000, 2)
    struct.pack_into("<I", sector, 100, 0xAABBCCDD)
    sector[108] = 9  # 512-byte sectors
    sector[109] = 3  # 8 sectors/cluster
    sector[110] = 1
    boot = parse_exfat_boot(bytes(sector))
    assert boot is not None
    assert boot.bytes_per_sector == 512
    assert boot.sectors_per_cluster == 8
    assert boot.root_dir_cluster == 2
    assert boot.cluster_size == 4096
