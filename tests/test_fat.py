from __future__ import annotations

from usb_recovery.devices.image import ImageSource
from usb_recovery.filesystems.fat import parse_fat_boot, scan_fat
from usb_recovery.filesystems.identifier import identify_boot_sector


def test_identify_fat16(fat_image: dict) -> None:
    assert fat_image["size"] % 512 == 0
    boot = fat_image["path"].read_bytes()[:512]
    assert identify_boot_sector(boot) == "fat16"
    parsed = parse_fat_boot(boot)
    assert parsed is not None
    assert parsed.kind == "fat16"


def test_recover_live_and_deleted(fat_image: dict) -> None:
    src = ImageSource(str(fat_image["path"]))
    with src:
        result = scan_fat(src, 0, include_existing=True)
    assert result is not None
    names = {c.name.upper() for c in result.candidates}
    assert "HELLO.TXT" in names
    assert any("SECRET" in n.upper() or n.upper().endswith(".TXT") for n in names)
    hello = next(c for c in result.candidates if c.name.upper() == "HELLO.TXT")
    assert hello.extra["content"] == fat_image["hello"]
    deleted = [c for c in result.candidates if c.status in {"deleted", "partial"}]
    assert deleted
    secret = next(c for c in deleted if b"deleted-secret" in c.extra.get("content", b""))
    assert secret.method == "metadata"


def test_contiguous_heuristic_for_zeroed_fat(fat_image: dict) -> None:
    src = ImageSource(str(fat_image["path"]))
    with src:
        result = scan_fat(src)
    assert result
    gone = [c for c in result.candidates if b"orphan-content" in c.extra.get("content", b"")]
    assert gone
    assert gone[0].status in {"deleted", "partial"}
