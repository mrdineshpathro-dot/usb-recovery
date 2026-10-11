"""Destination compatibility and pre-flight verification (237, 238)."""

from __future__ import annotations

import os
from pathlib import Path

from usb_recovery.exceptions import DestinationError
from usb_recovery.safety import destination_free_bytes
from usb_recovery.util import human_size, new_id

FAT32_MAX = 4 * 1024 * 1024 * 1024 - 1


def _fs_type(path: Path) -> tuple[str, int]:
    try:
        import os

        st = os.statvfs(path)
        # Linux f_namemax / f_frsize are useful; fstype needs /proc/mounts.
    except (OSError, AttributeError):
        st = None
    fstype = "unknown"
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as handle:
            best = ""
            for line in handle:
                parts = line.split()
                if len(parts) >= 3:
                    mount, kind = parts[1], parts[2]
                    if str(path).startswith(mount) and len(mount) >= len(best):
                        best, fstype = mount, kind
    except OSError:
        pass
    namemax = getattr(st, "f_namemax", 255) if st else 255
    return fstype, int(namemax)


def check_destination(
    dest: str | Path,
    *,
    needed_bytes: int = 0,
    largest_file: int = 0,
) -> dict:
    path = Path(dest)
    path.mkdir(parents=True, exist_ok=True)
    free = destination_free_bytes(path)
    fstype, namemax = _fs_type(path)
    issues: list[str] = []
    if needed_bytes and free < needed_bytes:
        issues.append(f"Need {human_size(needed_bytes)}, have {human_size(free)}")
    if fstype in {"vfat", "msdos", "fat", "exfat"} or fstype == "vfat":
        if largest_file > FAT32_MAX and fstype in {"vfat", "msdos", "fat"}:
            issues.append(
                f"Largest file {human_size(largest_file)} exceeds FAT32 4 GiB-1 limit on {fstype}"
            )
    return {
        "path": str(path),
        "free_bytes": free,
        "fstype": fstype,
        "namemax": namemax,
        "ok": not issues,
        "issues": issues,
    }


def verify_destination(dest: str | Path) -> dict:
    """Write and delete a tiny probe file to prove the destination is writable."""
    path = Path(dest)
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".ur-probe-{new_id()[:8]}"
    try:
        probe.write_bytes(b"USB-RECOVERY-LAB-PROBE")
        ok = probe.read_bytes() == b"USB-RECOVERY-LAB-PROBE"
        probe.unlink()
        if not ok:
            raise DestinationError(f"Destination probe mismatch at {path}")
        return {"ok": True, "path": str(path)}
    except OSError as exc:
        raise DestinationError(f"Destination {path} is not writable: {exc}") from exc
