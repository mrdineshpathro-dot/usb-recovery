from __future__ import annotations

from usb_recovery.devices.image import ImageSource
from usb_recovery.models import ScanOptions
from usb_recovery.partitions.map import analyze_partitions
from usb_recovery.recovery.engine import scan_source


def test_superfloppy_fat_is_not_empty_mbr(fat_image: dict) -> None:
    src = ImageSource(str(fat_image["path"]))
    with src:
        pmap = analyze_partitions(src)
        assert pmap.scheme == "none"
        assert pmap.partitions[0].start_lba == 0
        found = scan_source(src, ScanOptions.from_profile("quick"))
    names = {c.name.upper() for c in found}
    assert "HELLO.TXT" in names


def test_deep_carve_finds_png_without_directory_entry(fat_image: dict) -> None:
    src = ImageSource(str(fat_image["path"]))
    with src:
        found = scan_source(src, ScanOptions.from_profile("deep"))
    pngs = [c for c in found if c.file_type == "png" or c.mime == "image/png"]
    assert pngs
    assert any(c.method == "carved" for c in pngs)
