from __future__ import annotations

from pathlib import Path

from usb_recovery.devices.image import ImageSource
from usb_recovery.imaging.dd import image_source
from usb_recovery.util import sha256_file


def test_image_copy_and_hash(fat_image: dict, tmp_path: Path) -> None:
    dest = tmp_path / "copy.dd"
    src = ImageSource(str(fat_image["path"]))
    with src:
        result = image_source(src, dest, resume=False)
    assert result.bytes_written == fat_image["size"]
    assert dest.read_bytes() == fat_image["path"].read_bytes()
    assert result.sha256 == sha256_file(dest)
    assert result.bad_sectors == []
