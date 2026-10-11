from __future__ import annotations

from usb_recovery.devices.image import ImageSource
from usb_recovery.partitions.gpt import parse_gpt_header
from usb_recovery.partitions.map import analyze_partitions


def test_gpt_header(gpt_image: dict) -> None:
    data = gpt_image["path"].read_bytes()
    hdr = parse_gpt_header(data[512:1024])
    assert hdr.signature_valid
    assert hdr.current_lba == 1


def test_analyze_gpt(gpt_image: dict) -> None:
    src = ImageSource(str(gpt_image["path"]))
    with src:
        pmap = analyze_partitions(src)
    assert pmap.scheme == "gpt"
    assert pmap.partitions
    assert pmap.partitions[0].start_lba == 34
