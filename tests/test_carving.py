from __future__ import annotations

from usb_recovery.carving.carver import carve_source
from usb_recovery.carving.validators import validate_jpeg, validate_pdf, validate_png, validate_zip
from usb_recovery.devices.image import ImageSource
from usb_recovery.models import ScanOptions
from tests.fixtures.builder import minimal_jpeg, minimal_pdf, minimal_png, minimal_zip


def test_validators_roundtrip() -> None:
    ok, _ = validate_jpeg(minimal_jpeg())
    assert ok
    ok, _ = validate_png(minimal_png())
    assert ok
    ok, _ = validate_pdf(minimal_pdf())
    assert ok
    ok, _ = validate_zip(minimal_zip())
    assert ok


def test_carve_planted_files(carve_image: dict) -> None:
    src = ImageSource(str(carve_image["path"]))
    options = ScanOptions.from_profile("deep")
    with src:
        hits = carve_source(src, options)
    kinds = {h.file_type for h in hits}
    assert "jpg" in kinds or "jpeg" in kinds
    assert "png" in kinds
    assert "pdf" in kinds
    assert "zip" in kinds
    jpeg = next(h for h in hits if h.file_type in {"jpg", "jpeg"})
    assert jpeg.source_offset == 1024
    assert jpeg.extra["content"].startswith(b"\xff\xd8")
    assert jpeg.confidence > 20
