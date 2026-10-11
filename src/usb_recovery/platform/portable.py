"""Portable application mode (291). Settings live next to the program or USB_RECOVERY_HOME."""

from __future__ import annotations

import os
from pathlib import Path

from usb_recovery.constants import APP_ID


def use_portable_mode() -> bool:
    if os.environ.get("USB_RECOVERY_PORTABLE") == "1":
        return True
    marker = Path.cwd() / "usb-recovery-data"
    return marker.is_dir() or (Path.cwd() / "portable.txt").exists()


def portable_paths(root: Path | None = None) -> dict[str, Path]:
    if root is None:
        env = os.environ.get("USB_RECOVERY_HOME")
        root = Path(env) if env else (Path.cwd() / "usb-recovery-data")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "root": root,
        "config": root / "config.toml",
        "logs": root / "logs",
        "db": root / f"{APP_ID}.sqlite",
        "sessions": root / "sessions",
    }
    paths["logs"].mkdir(exist_ok=True)
    paths["sessions"].mkdir(exist_ok=True)
    return paths
