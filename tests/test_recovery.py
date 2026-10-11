from __future__ import annotations

from pathlib import Path

from usb_recovery.devices.image import ImageSource
from usb_recovery.models import ScanOptions
from usb_recovery.recovery.engine import recover_candidates, scan_source


def test_end_to_end_scan_and_recover(mbr_image: dict, tmp_path: Path) -> None:
    src = ImageSource(str(mbr_image["path"]))
    options = ScanOptions.from_profile("standard")
    with src:
        found = scan_source(src, options)
        assert found
        hello = next(c for c in found if c.name.upper() == "HELLO.TXT")
        dest = tmp_path / "out"
        results = recover_candidates(src, [hello], dest)
    assert results[0].status in {"recovered", "partial"}
    written = list(dest.rglob("HELLO.TXT"))
    assert written
    assert b"Hello, USB Recovery Lab" in written[0].read_bytes()


def test_no_overwrite(mbr_image: dict, tmp_path: Path) -> None:
    src = ImageSource(str(mbr_image["path"]))
    options = ScanOptions.from_profile("quick")
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "HELLO.TXT").write_text("existing")
    with src:
        found = scan_source(src, options)
        hello = next(c for c in found if c.name.upper() == "HELLO.TXT")
        recover_candidates(src, [hello], dest)
    assert (dest / "HELLO.TXT").read_text() == "existing"
    alts = list(dest.glob("HELLO (*).TXT")) + list(dest.glob("HELLO*.TXT"))
    assert any(p.name != "HELLO.TXT" for p in dest.iterdir())
