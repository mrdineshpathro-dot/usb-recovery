"""Sparse image hole map (feature 265). Linux SEEK_HOLE / SEEK_DATA."""

from __future__ import annotations

import os
from pathlib import Path


def sparse_map(path: str | Path, *, max_ranges: int = 4096) -> dict:
    """Return data/hole ranges. On platforms without SEEK_HOLE, the whole file is data."""
    p = Path(path)
    size = p.stat().st_size
    seek_hole = getattr(os, "SEEK_HOLE", None)
    seek_data = getattr(os, "SEEK_DATA", None)
    if seek_hole is None or seek_data is None:
        return {
            "path": str(p),
            "size": size,
            "supported": False,
            "data": [{"start": 0, "end": size}] if size else [],
            "holes": [],
            "note": "OS does not expose SEEK_HOLE; treating the image as fully allocated.",
        }
    data: list[dict] = []
    holes: list[dict] = []
    with open(p, "rb") as handle:
        fd = handle.fileno()
        pos = 0
        while pos < size and len(data) + len(holes) < max_ranges:
            try:
                data_at = os.lseek(fd, pos, seek_data)
            except OSError:
                holes.append({"start": pos, "end": size})
                break
            if data_at > pos:
                holes.append({"start": pos, "end": data_at})
            try:
                hole_at = os.lseek(fd, data_at, seek_hole)
            except OSError:
                data.append({"start": data_at, "end": size})
                break
            data.append({"start": data_at, "end": hole_at})
            pos = hole_at
            if hole_at <= data_at:
                break
    return {
        "path": str(p),
        "size": size,
        "supported": True,
        "data": data,
        "holes": holes,
        "omitted_bytes": sum(h["end"] - h["start"] for h in holes),
    }
