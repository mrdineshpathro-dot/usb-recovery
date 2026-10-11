"""Transactional writes and leftover partial cleanup (231, 232)."""

from __future__ import annotations

import os
from pathlib import Path


PARTIAL_SUFFIX = ".ur-partial"


def write_transactional(dest: Path, data: bytes) -> Path:
    """Write to dest.ur-partial then atomically replace dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + PARTIAL_SUFFIX)
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(dest)
    return dest


def cleanup_partials(root: str | Path) -> list[str]:
    removed: list[str] = []
    base = Path(root)
    if not base.exists():
        return removed
    for path in base.rglob(f"*{PARTIAL_SUFFIX}"):
        try:
            path.unlink()
            removed.append(str(path))
        except OSError:
            continue
    return removed
