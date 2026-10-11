from __future__ import annotations

from pathlib import Path

import pytest

from usb_recovery.constants import DEVICE_CONFIRM_TOKEN
from usb_recovery.exceptions import ConfirmationRequired, DestinationError, SafetyError
from usb_recovery.safety import (
    assert_destination_safe,
    open_readonly_fd,
    refuse_destructive_command,
    require_device_confirmation,
    warn_failing_media,
)


def test_require_confirmation_for_physical() -> None:
    with pytest.raises(ConfirmationRequired):
        require_device_confirmation(None, is_physical=True)
    require_device_confirmation(DEVICE_CONFIRM_TOKEN, is_physical=True)
    require_device_confirmation(None, is_physical=False)


def test_open_readonly(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    fd = open_readonly_fd(f)
    try:
        import os

        assert os.read(fd, 3) == b"abc"
    finally:
        import os

        os.close(fd)


def test_refuse_destructive() -> None:
    with pytest.raises(SafetyError):
        refuse_destructive_command("mkfs.vfat /dev/sdb")
    with pytest.raises(SafetyError):
        refuse_destructive_command("diskpart clean")
    refuse_destructive_command("ls /dev/sdb")


def test_same_path_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src.img"
    src.write_bytes(b"x" * 512)
    with pytest.raises(SafetyError):
        assert_destination_safe(src, src, needed_bytes=0)


def test_image_file_may_recover_to_same_disk(tmp_path: Path) -> None:
    src = tmp_path / "src.img"
    src.write_bytes(b"x" * 512)
    dest = tmp_path / "recovered" / "file.bin"
    assert_destination_safe(src, dest, needed_bytes=512)


def test_destination_space_check(tmp_path: Path) -> None:
    src = tmp_path / "src.img"
    src.write_bytes(b"x" * 512)
    dest = tmp_path / "out" / "file.bin"
    huge = 10**18
    with pytest.raises(DestinationError):
        assert_destination_safe(src, dest, needed_bytes=huge, prevent_same_device=False)


def test_failing_media_warning() -> None:
    assert warn_failing_media(3, 64) is None
    msg = warn_failing_media(100, 64)
    assert msg and "unreadable" in msg
