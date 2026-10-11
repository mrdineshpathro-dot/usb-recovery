"""Resource-leak detection helpers (307)."""

from __future__ import annotations

import os
from pathlib import Path


def fd_snapshot() -> set[str]:
    proc = Path("/proc/self/fd")
    if not proc.is_dir():
        return set()
    names: set[str] = set()
    for entry in proc.iterdir():
        try:
            names.add(os.readlink(entry))
        except OSError:
            names.add(entry.name)
    return names


def leak_delta(before: set[str], after: set[str]) -> dict:
    leaked = sorted(after - before)
    return {"leaked": leaked, "count": len(leaked), "ok": not leaked}
