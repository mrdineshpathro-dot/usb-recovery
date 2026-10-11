"""Recovery benchmark against known synthetic datasets (256, 257)."""

from __future__ import annotations

import time
from pathlib import Path

from usb_recovery.devices.image import ImageSource
from usb_recovery.models import ScanOptions
from usb_recovery.recovery.engine import scan_source


def run_benchmark(image: Path, *, expect_names: list[str] | None = None, profile: str = "standard") -> dict:
    t0 = time.perf_counter()
    src = ImageSource(str(image))
    with src:
        found = scan_source(src, ScanOptions.from_profile(profile))  # type: ignore[arg-type]
    elapsed = time.perf_counter() - t0
    names = {c.name.upper() for c in found}
    missing = []
    if expect_names:
        missing = [n for n in expect_names if n.upper() not in names]
    return {
        "image": str(image),
        "seconds": elapsed,
        "candidates": len(found),
        "bytes_per_s": (src.size / elapsed) if elapsed else 0,
        "missing_expected": missing,
        "regression_ok": not missing,
    }
