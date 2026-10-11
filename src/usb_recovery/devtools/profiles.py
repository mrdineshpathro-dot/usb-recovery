"""Reproducible scan profiles (308)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from usb_recovery.models import ScanOptions
from usb_recovery.util import isoformat


def dump_scan_profile(options: ScanOptions, path: Path, *, source: str | None = None) -> Path:
    payload = {
        "saved_at": isoformat(),
        "source": source,
        "options": asdict(options),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_scan_profile(path: Path) -> ScanOptions:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("options") or data
    options = ScanOptions.from_profile(raw.get("profile") or "standard")
    for key, value in raw.items():
        if hasattr(options, key) and key != "profile":
            if key == "sector_range" and isinstance(value, list):
                value = tuple(value)
            setattr(options, key, value)
    return options
