"""First-run setup checks (292)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from usb_recovery.safety import destination_free_bytes
from usb_recovery.util import human_size


def first_run_checks(dest: str | Path | None = None) -> dict:
    issues: list[str] = []
    notes: list[str] = []
    if sys.version_info < (3, 11):
        issues.append(f"Python {sys.version.split()[0]} is older than 3.11")
    else:
        notes.append(f"Python {sys.version.split()[0]} OK")
    notes.append(f"Platform {sys.platform}")
    gui = True
    try:
        import PySide6  # noqa: F401
    except ImportError:
        gui = False
        notes.append("PySide6 not installed; CLI-only mode")
    if os.name == "posix" and os.geteuid() != 0:
        notes.append("Not running as root; physical /dev/sdX access may fail")
    if dest:
        path = Path(dest)
        path.mkdir(parents=True, exist_ok=True)
        free = destination_free_bytes(path)
        notes.append(f"Destination free space {human_size(free)}")
        if free < 64 * 1024 * 1024:
            issues.append("Destination has less than 64 MiB free")
        probe = path / ".ur-setup-probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            issues.append(f"Destination not writable: {exc}")
    clam = shutil.which("clamscan")
    notes.append("clamscan available" if clam else "clamscan not on PATH (optional)")
    return {
        "ok": not issues,
        "gui": gui,
        "issues": issues,
        "notes": notes,
        "python": sys.version.split()[0],
    }
