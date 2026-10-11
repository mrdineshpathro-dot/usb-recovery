"""Mandatory data-safety controls.

A read-only file descriptor does **not** guarantee that the operating system,
USB bridge, or flash controller will perform zero writes. Live filesystems may
still be journaled by the OS if they remain mounted. For high-value forensic
work, image the device in a controlled acquisition environment and work from
the image.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from usb_recovery.constants import DEVICE_CONFIRM_TOKEN
from usb_recovery.exceptions import ConfirmationRequired, DestinationError, SafetyError
from usb_recovery.logging_config import get_logger
from usb_recovery.util import file_device_id, human_size, parent_existing

log = get_logger("safety")

_DESTRUCTIVE_TOKENS = (
    "diskpart",
    "format ",
    "mkfs",
    "mkfs.",
    "wipefs",
    "dd of=",
    "clean all",
    "blkdiscard",
    "cipher /w",
)


def is_block_device(path: str | os.PathLike[str]) -> bool:
    try:
        mode = os.stat(path, follow_symlinks=True).st_mode
    except OSError:
        return False
    return stat.S_ISBLK(mode) or stat.S_ISCHR(mode)


def open_readonly_fd(path: str | os.PathLike[str]) -> int:
    """Open `path` with O_RDONLY (and O_CLOEXEC / O_BINARY when available)."""
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_BINARY", 0)
    # Never add O_RDWR / O_WRONLY / O_CREAT.
    try:
        return os.open(os.fspath(path), flags)
    except OSError as exc:
        raise SafetyError(f"Unable to open {path} read-only: {exc}") from exc


def assert_fd_read_only(fd: int) -> None:
    """Best-effort check that the descriptor was not opened for writing."""
    try:
        access = os.O_ACCMODE  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - windows
        access = 3
    try:
        import fcntl  # type: ignore[import-not-found]

        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if (flags & access) != os.O_RDONLY:
            raise SafetyError("Source file descriptor is not read-only")
    except ImportError:
        return
    except OSError:
        return


def require_device_confirmation(confirm: str | None, *, is_physical: bool) -> None:
    if not is_physical:
        return
    if confirm != DEVICE_CONFIRM_TOKEN:
        raise ConfirmationRequired(
            "Opening a physical device requires --confirm "
            f"{DEVICE_CONFIRM_TOKEN} (or the GUI confirmation checkbox). "
            "The application will still open the device read-only, but the OS "
            "may write if the volume stays mounted."
        )


def same_physical_storage(source: str | os.PathLike[str], dest: str | os.PathLike[str]) -> bool:
    """Return True when dest lives on the same underlying device as source.

    Disk *images* are ordinary files: recovering onto the same hard disk that
    holds the image is expected and allowed. The forbidden case is writing
    recovered files onto a *block device* (the pen drive) that is the source,
    or onto a filesystem whose ``st_dev`` equals that device's ``st_rdev``.
    """
    src = Path(source)
    dst_existing = parent_existing(dest)
    src_stat = file_device_id(src)
    dst_stat = file_device_id(dst_existing)
    if src_stat is None or dst_stat is None:
        return False

    source_is_block = is_block_device(src)
    if not source_is_block:
        # Image file: path-equality is enforced separately. Same HDD is OK.
        return False

    try:
        src_rdev = os.stat(src, follow_symlinks=True).st_rdev
    except OSError:
        src_rdev = 0
    if src_rdev and src_rdev == dst_stat[0]:
        return True
    if src_stat[0] == dst_stat[0]:
        return True
    return False


def assert_destination_safe(
    source: str | os.PathLike[str],
    dest: str | os.PathLike[str],
    *,
    needed_bytes: int = 0,
    prevent_same_device: bool = True,
    allow_same_device: bool = False,
) -> None:
    dest_path = Path(dest)
    if dest_path.exists() and dest_path.is_file() and dest_path.resolve() == Path(source).resolve():
        raise SafetyError("Destination path is the source path")

    if prevent_same_device and not allow_same_device:
        try:
            if same_physical_storage(source, dest_path):
                raise SafetyError(
                    "Destination is on the same physical storage as the source. "
                    "Recovered files must be saved to a different disk. "
                    "Pass --allow-same-device only if you accept the risk of overwriting evidence."
                )
        except SafetyError:
            raise
        except OSError as exc:
            log.warning("same-device check failed: %s", exc)

    parent = dest_path if dest_path.is_dir() else dest_path.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DestinationError(f"Cannot create destination {parent}: {exc}") from exc

    if needed_bytes > 0:
        free = destination_free_bytes(parent)
        if free < needed_bytes:
            raise DestinationError(
                f"Destination has {human_size(free)} free but "
                f"{human_size(needed_bytes)} is required"
            )


def destination_free_bytes(path: str | os.PathLike[str]) -> int:
    parent = parent_existing(path)
    try:
        usage = os.statvfs(parent)
        return int(usage.f_bavail * usage.f_frsize)
    except (OSError, AttributeError):
        # Windows fallback.
        if os.name == "nt":  # pragma: no cover
            import ctypes

            free = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(  # type: ignore[attr-defined]
                str(parent), None, None, ctypes.byref(free)
            )
            return int(free.value)
        raise DestinationError(f"Cannot determine free space for {path}")


def refuse_destructive_command(command: str) -> None:
    lowered = command.lower()
    for token in _DESTRUCTIVE_TOKENS:
        if token in lowered:
            raise SafetyError(
                f"Refusing to run potentially destructive command containing {token!r}. "
                "USB Recovery Lab never formats, repairs, or initializes source devices."
            )


def warn_failing_media(bad_sector_count: int, threshold: int) -> str | None:
    if bad_sector_count >= threshold:
        return (
            f"{bad_sector_count} unreadable sectors were encountered. "
            "Continued reading of a failing flash device can make remaining "
            "data unrecoverable. Prefer stopping and imaging with extra retries "
            "only if the case value justifies the risk."
        )
    return None
