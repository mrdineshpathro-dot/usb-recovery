from __future__ import annotations

from usb_recovery.devices.image import ImageSource
from usb_recovery.partitions.map import analyze_partitions
from usb_recovery.partitions.mbr import parse_mbr


def test_mbr_signature_and_partition(mbr_image: dict) -> None:
    data = mbr_image["path"].read_bytes()[:512]
    table = parse_mbr(data)
    assert table.signature_valid
    assert any(e.type_id == 0x0E and e.start_lba == 8 for e in table.entries)


def test_analyze_mbr_image(mbr_image: dict) -> None:
    src = ImageSource(str(mbr_image["path"]))
    with src:
        pmap = analyze_partitions(src)
    assert pmap.scheme == "mbr"
    assert pmap.partitions
    assert pmap.partitions[0].start_lba == 8
