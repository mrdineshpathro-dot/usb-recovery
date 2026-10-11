"""Repeatable, versioned analysis pipeline (353)."""

from __future__ import annotations

import json
from pathlib import Path

from usb_recovery.constants import APP_VERSION
from usb_recovery.util import isoformat

PIPELINE_VERSION = "1.0"

DEFAULT_STEPS = [
    {"id": "identify", "version": "1.0", "module": "filesystems.identifier"},
    {"id": "partitions", "version": "1.0", "module": "partitions.map"},
    {"id": "metadata", "version": "1.0", "module": "filesystems"},
    {"id": "carve", "version": "1.0", "module": "carving.carver"},
    {"id": "validate", "version": "1.0", "module": "forensics.validate"},
]


def save_pipeline(path: str | Path, *, steps: list[dict] | None = None, params: dict | None = None) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline_version": PIPELINE_VERSION,
        "app_version": APP_VERSION,
        "created_at": isoformat(),
        "steps": steps or DEFAULT_STEPS,
        "params": params or {},
        "note": "Re-running with the same params and app version is intended to be repeatable on the same image.",
    }
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def run_pipeline(source: str | Path, dest_dir: str | Path, *, params: dict | None = None) -> dict:
    """Execute versioned steps on a disk image. Never writes to the source."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    spec = save_pipeline(dest / "pipeline.json", params=params)
    from usb_recovery.devices.image import ImageSource
    from usb_recovery.filesystems.identifier import identify_boot_sector
    from usb_recovery.forensics.validate import independent_validate
    from usb_recovery.models import ScanOptions
    from usb_recovery.partitions.map import analyze_partitions
    from usb_recovery.recovery.engine import scan_source

    source_path = str(source)
    results: list[dict] = []
    with ImageSource(source_path) as src:
        kind = identify_boot_sector(src.read(0, 512))
        results.append({"id": "identify", "filesystem": kind})
        pmap = analyze_partitions(src)
        results.append({"id": "partitions", "scheme": pmap.scheme, "count": len(pmap.partitions)})
        options = ScanOptions.from_profile((params or {}).get("profile", "quick"))
        found = scan_source(src, options)
        results.append({"id": "metadata+carve", "candidates": len(found)})
        validations = independent_validate(found)
        results.append({"id": "validate", "checked": len(validations)})
    summary = {
        "source": source_path,
        "pipeline": str(spec),
        "app_version": APP_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "steps": results,
        "params": params or {},
    }
    (dest / "pipeline-result.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
